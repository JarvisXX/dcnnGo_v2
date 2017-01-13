from __future__ import print_function
from collections import namedtuple
from itertools import count
from functools import reduce
from multiprocessing.pool import Pool
import numpy as np
import DCNN
import math
import multiprocessing
import random
import re
import sys
import time
import copy

# Given a board of size NxN (N=9, 19, ...), we represent the position
# as an (N+1)*(N+2) string, with '.' (empty), 'X' (to-play player),
# 'x' (other player), and whitespace (off-board border to make rules
# implementation easier).  Coordinates are just indices in this string.
# You can simply print(board) when debugging.
N = 19
W = N + 2

empty = "\n".join([(N+1)*' '] + N*[' '+N*'.'] + [(N+2)*' '])
colstr = 'ABCDEFGHJKLMNOPQRST'
MAX_GAME_LEN = N * N * 3

N_SIMS = 400
RAVE_EQUIV = 3500
EXPAND_VISITS = 8
#?? what is this? why 10?
PRIOR_EVEN = 10  # should be even number; 0.5 prior
PRIOR_SELFATARI = 10  # negative prior
PRIOR_CAPTURE_ONE = 15
PRIOR_CAPTURE_MANY = 30
PRIOR_PAT3 = 10
PRIOR_LARGEPATTERN = 100  # most moves have relatively small probability
PRIOR_CFG = [24, 22, 8]  # priors for moves in cfg dist. 1, 2, 3
PRIOR_EMPTYAREA = 10
REPORT_PERIOD = 200
PROB_HEURISTIC = {'capture': 0.9, 'pat3': 0.95}  # probability of heuristic suggestions being taken in playout
PROB_SSAREJECT = 0.9  # probability of rejecting suggested self-atari in playout
PROB_RSAREJECT = 0.5  # probability of rejecting random self-atari in playout; this is lower than above to allow nakade
RESIGN_THRES = 0.2
FASTPLAY20_THRES = 0.8  # if at 20% playouts winrate is >this, stop reading
FASTPLAY5_THRES = 0.95  # if at 5% playouts winrate is >this, stop reading
CPUCT = 1 #TBD

model = None

pat3src = [  # 3x3 playout patterns; X,O are colors, x,o are their inverses
       ["XOX",  # hane pattern - enclosing hane
        "...",
        "???"],
       ["XO.",  # hane pattern - non-cutting hane
        "...",
        "?.?"],
       ["XO?",  # hane pattern - magari
        "X..",
        "x.?"],
       # ["XOO",  # hane pattern - thin hane
       #  "...",
       #  "?.?", "X",  - only for the X player
       [".O.",  # generic pattern - katatsuke or diagonal attachment; similar to magari
        "X..",
        "..."],
       ["XO?",  # cut1 pattern (kiri] - unprotected cut
        "O.o",
        "?o?"],
       ["XO?",  # cut1 pattern (kiri] - peeped cut
        "O.X",
        "???"],
       ["?X?",  # cut2 pattern (de]
        "O.O",
        "ooo"],
       ["OX?",  # cut keima
        "o.O",
        "???"],
       ["X.?",  # side pattern - chase
        "O.?",
        "   "],
       ["OX?",  # side pattern - block side cut
        "X.O",
        "   "],
       ["?X?",  # side pattern - block side connection
        "x.O",
        "   "],
       ["?XO",  # side pattern - sagari
        "x.x",
        "   "],
       ["?OX",  # side pattern - cut
        "X.O",
        "   "],
       ]

pat_gridcular_seq = [  # Sequence of coordinate offsets of progressively wider diameters in gridcular metric
        [[0,0],
         [0,1], [0,-1], [1,0], [-1,0],
         [1,1], [-1,1], [1,-1], [-1,-1], ],  # d=1,2 is not considered separately
        [[0,2], [0,-2], [2,0], [-2,0], ],
        [[1,2], [-1,2], [1,-2], [-1,-2], [2,1], [-2,1], [2,-1], [-2,-1], ],
        [[0,3], [0,-3], [2,2], [-2,2], [2,-2], [-2,-2], [3,0], [-3,0], ],
        [[1,3], [-1,3], [1,-3], [-1,-3], [3,1], [-3,1], [3,-1], [-3,-1], ],
        [[0,4], [0,-4], [2,3], [-2,3], [2,-3], [-2,-3], [3,2], [-3,2], [3,-2], [-3,-2], [4,0], [-4,0], ],
        [[1,4], [-1,4], [1,-4], [-1,-4], [3,3], [-3,3], [3,-3], [-3,-3], [4,1], [-4,1], [4,-1], [-4,-1], ],
        [[0,5], [0,-5], [2,4], [-2,4], [2,-4], [-2,-4], [4,2], [-4,2], [4,-2], [-4,-2], [5,0], [-5,0], ],
        [[1,5], [-1,5], [1,-5], [-1,-5], [3,4], [-3,4], [3,-4], [-3,-4], [4,3], [-4,3], [4,-3], [-4,-3], [5,1], [-5,1], [5,-1], [-5,-1], ],
        [[0,6], [0,-6], [2,5], [-2,5], [2,-5], [-2,-5], [4,4], [-4,4], [4,-4], [-4,-4], [5,2], [-5,2], [5,-2], [-5,-2], [6,0], [-6,0], ],
        [[1,6], [-1,6], [1,-6], [-1,-6], [3,5], [-3,5], [3,-5], [-3,-5], [5,3], [-5,3], [5,-3], [-5,-3], [6,1], [-6,1], [6,-1], [-6,-1], ],
        [[0,7], [0,-7], [2,6], [-2,6], [2,-6], [-2,-6], [4,5], [-4,5], [4,-5], [-4,-5], [5,4], [-5,4], [5,-4], [-5,-4], [6,2], [-6,2], [6,-2], [-6,-2], [7,0], [-7,0], ],
    ]
spat_patterndict_file = 'patterns.spat'
large_patterns_file = 'patterns.prob'


#######################
# board string routines

# four neighbors
def neighbors(c):
    """ generator of coordinates for all neighbors of c """
    return [c-1, c+1, c-W, c+W]

# four corner of neighbors
def diag_neighbors(c):
    """ generator of coordinates for all diagonal neighbors of c """
    return [c-W-1, c-W+1, c+W-1, c+W+1]

# put p(x or X) at coordinate c on board
def board_put(board, c, p):
    return board[:c] + p + board[c+1:]

# replace continuous area with color c using '#'
#?? but why byteboard?
def floodfill(board, c):
    """ replace continuous-color area starting at c with special color # """
    # This is called so much that a bytearray is worthwhile...
    byteboard = bytearray(board, 'utf8')
    p = byteboard[c]
    byteboard[c] = ord('#')
    fringe = [c]
    while fringe:
        c = fringe.pop()
        for d in neighbors(c):
            if byteboard[d] == p:
                byteboard[d] = ord('#')
                fringe.append(d)
    return str(byteboard, 'utf8')

# all types that is neighbour of '#'
# Regex that matches various kind of points adjecent to '#' (floodfilled) points
# return the index of matchobject p
contact_res = dict()
for p in ['.', 'x', 'X']:
    rp = '\\.' if p == '.' else p
    contact_res_src = ['#' + rp,  # p at right
                       rp + '#',  # p at left
                       '#' + '.'*(W-1) + rp,  # p below
                       rp + '.'*(W-1) + '#']  # p above
    contact_res[p] = re.compile('|'.join(contact_res_src), flags=re.DOTALL)

def contact(board, p):
    """ test if point of color p is adjecent to color # anywhere
    on the board; use in conjunction with floodfill for reachability """
    m = contact_res[p].search(board)
    if not m:
        return None
    return m.start() if (m.group(0)[0] == p) else (m.end() - 1)

# whether is eye-like shape
def is_eyeish(board, c):
    """ test if c is inside a single-color diamond and return the diamond
    color or None; this could be an eye, but also a false one """
    eyecolor = None
    for d in neighbors(c):
        if board[d].isspace():
            continue
        if board[d] == '.':
            return None
        if eyecolor is None:
            eyecolor = board[d]
            othercolor = eyecolor.swapcase()
        elif board[d] == othercolor:
            return None
    return eyecolor

# whether is eye
def is_eye(board, c):
    """ test if c is an eye and return its color or None """
    eyecolor = is_eyeish(board, c)
    if eyecolor is None:
        return None

    # Eye-like shape, but it could be a falsified eye
    falsecolor = eyecolor.swapcase()
    false_count = 0
    at_edge = False
    for d in diag_neighbors(c):
        if board[d].isspace():
            at_edge = True
        elif board[d] == falsecolor:
            false_count += 1
    if at_edge:
        false_count += 1
    if false_count >= 2:
        return None

    return eyecolor

# Position, a state of now for to-play player, includes many info
# cap(X,x), the number of total captures of color (X,x)
# ko, the coordinate of 'jie', input ko means last ko and cannot move in
# change: whether the next_stone has been changed
class Position(namedtuple('Position', 'board cap n ko last last2 komi')):
    """ Implementation of simple Chinese Go rules;
    n is how many moves were played so far """

    # play in c, and capture, set ko, then update
    # position of play in coord c, check ko or suicide
    def move(self, c):
        """ play as player X at the given coord c, return the new position """

        # Test for ko
        if c == self.ko:
            return None
        # Are we trying to play in enemy's eye?
        in_enemy_eye = is_eyeish(self.board, c) == 'x'

        board = board_put(self.board, c, 'X')
        # Test for captures, and track ko
        capX = self.cap[0]
        singlecaps = []
        for d in neighbors(c):
            if board[d] != 'x':
                continue
            # XXX: The following is an extremely naive and SLOW approach
            # at things - to do it properly, we should maintain some per-group
            # data structures tracking liberties.
            fboard = floodfill(board, d)  # get a board with the adjecent group replaced by '#'
            if contact(fboard, '.') is not None:
                continue  # some liberties left
            # no liberties left for this group, remove the stones!
            capcount = fboard.count('#')
            if capcount == 1:
                singlecaps.append(d)
            capX += capcount
            board = fboard.replace('#', '.')  # capture the group
        # Set ko
        ko = singlecaps[0] if in_enemy_eye and len(singlecaps) == 1 else None
        # Test for suicide
        if contact(floodfill(board, c), '.') is None:
            return None

        # Update the position and return
        return Position(board=board.swapcase(), cap=(self.cap[1], capX),
                        n=self.n + 1, ko=ko, last=c, last2=self.last, komi=self.komi)

    def pass_move(self):
        """ pass - i.e. return simply a flipped position """
        return Position(board=self.board.swapcase(), cap=(self.cap[1], self.cap[0]),
                        n=self.n + 1, ko=None, last=None, last2=self.last, komi=self.komi)

    def moves(self, i0):
        """ Generate a list of moves (includes false positives - suicide moves;
        does not include true-eye-filling moves), starting from a given board
        index (that can be used for randomization) """
        i = i0-1
        passes = 0
        while True:
            i = self.board.find('.', i+1)
            if passes > 0 and (i == -1 or i >= i0):
                break  # we have looked through the whole board
            elif i == -1:
                i = 0
                passes += 1
                continue  # go back and start from the beginning
            # Test for to-play player's one-point eye
            if is_eye(self.board, i) == 'X':
                continue
            yield i

    # list of neighbor and corner neighbor in random order
    def last_moves_neighbors(self):
        """ generate a randomly shuffled list of points including and
        surrounding the last two moves (but with the last move having
        priority) """
        clist = []
        for c in self.last, self.last2:
            if c is None:  continue
            dlist = [c] + list(neighbors(c) + diag_neighbors(c))
            random.shuffle(dlist)
            clist += [d for d in dlist if d not in clist]
        return clist

    #?? do not check
    def score(self, owner_map=None):
        """ compute score for to-play player; this assumes a final position
        with all dead stones captured; if owner_map is passed, it is assumed
        to be an array of statistics with average owner at the end of the game
        (+1 black, -1 white) """
        board = self.board
        i = 0
        while True:
            i = self.board.find('.', i+1)
            if i == -1:
                break
            fboard = floodfill(board, i)
            # fboard is board with some continuous area of empty space replaced by #
            touches_X = contact(fboard, 'X') is not None
            touches_x = contact(fboard, 'x') is not None
            if touches_X and not touches_x:
                board = fboard.replace('#', 'X')
            elif touches_x and not touches_X:
                board = fboard.replace('#', 'x')
            else:
                board = fboard.replace('#', ':')  # seki, rare
            # now that area is replaced either by X, x or :
        komi = self.komi if self.n % 2 == 1 else -self.komi
        if owner_map is not None:
            for c in range(W*W):
                n = 1 if board[c] == 'X' else -1 if board[c] == 'x' else 0
                owner_map[c] += n * (1 if self.n % 2 == 0 else -1)
        return board.count('X') - board.count('x') + komi

    def setchange(self, value):
        self.change = value

def empty_position():
    """ Return an initial board position """
    return Position(board=empty, cap=(0, 0), n=0, ko=None, last=None, last2=None, komi=6.5)


###############
# go heuristics

def fix_atari(pos, c, singlept_ok=False, twolib_test=True, twolib_edgeonly=False):

    def read_ladder_attack(pos, c, l1, l2):
        """ check if a capturable ladder is being pulled out at c and return
        a move that continues it in that case; expects its two liberties as
        l1, l2  (in fact, this is a general 2-lib capture exhaustive solver) """
        for l in [l1, l2]:
            pos_l = pos.move(l)
            if pos_l is None:
                continue
            # fix_atari() will recursively call read_ladder_attack() back;
            # however, ignore 2lib groups as we don't have time to chase them
            is_atari, atari_escape = fix_atari(pos_l, c, twolib_test=False)
            if is_atari and not atari_escape:
                return l
        return None

    fboard = floodfill(pos.board, c)
    group_size = fboard.count('#')
    if singlept_ok and group_size == 1:
        return (False, [])
    # Find a liberty
    l = contact(fboard, '.')
    # Ok, any other liberty?
    fboard = board_put(fboard, l, 'L')
    l2 = contact(fboard, '.')
    if l2 is not None:
        # At least two liberty group...
        if twolib_test and group_size > 1 \
           and (not twolib_edgeonly or line_height(l) == 0 and line_height(l2) == 0) \
           and contact(board_put(fboard, l2, 'L'), '.') is None:
            # Exactly two liberty group with more than one stone.  Check
            # that it cannot be caught in a working ladder; if it can,
            # that's as good as in atari, a capture threat.
            # (Almost - N/A for countercaptures.)
            ladder_attack = read_ladder_attack(pos, c, l, l2)
            if ladder_attack:
                return (False, [ladder_attack])
        return (False, [])

    # In atari! If it's the opponent's group, that's enough...
    if pos.board[c] == 'x':
        return (True, [l])

    solutions = []

    # Before thinking about defense, what about counter-capturing
    # a neighboring group?
    ccboard = fboard
    while True:
        othergroup = contact(ccboard, 'x')
        if othergroup is None:
            break
        a, ccls = fix_atari(pos, othergroup, twolib_test=False)
        if a and ccls:
            solutions += ccls
        # XXX: floodfill is better for big groups
        ccboard = board_put(ccboard, othergroup, '%')

    # We are escaping.  Will playing our last liberty gain
    # at least two liberties?  Re-floodfill to account for connecting
    escpos = pos.move(l)
    if escpos is None:
        return (True, solutions)  # oops, suicidal move
    fboard = floodfill(escpos.board, l)
    l_new = contact(fboard, '.')
    fboard = board_put(fboard, l_new, 'L')
    l_new_2 = contact(fboard, '.')
    if l_new_2 is not None:
        # Good, there is still some liberty remaining - but if it's
        # just the two, check that we are not caught in a ladder...
        # (Except that we don't care if we already have some alternative
        # escape routes!)
        if solutions or not (contact(board_put(fboard, l_new_2, 'L'), '.') is None
                             and read_ladder_attack(escpos, l, l_new, l_new_2) is not None):
            solutions.append(l)

    return (True, solutions)


def cfg_distances(board, c):
    """ return a board map listing common fate graph distances from
    a given point - this corresponds to the concept of locality while
    contracting groups to single points """
    cfg_map = W*W*[-1]
    cfg_map[c] = 0

    # flood-fill like mechanics
    fringe = [c]
    while fringe:
        c = fringe.pop()
        for d in neighbors(c):
            if board[d].isspace() or 0 <= cfg_map[d] <= cfg_map[c]:
                continue
            cfg_before = cfg_map[d]
            if board[d] != '.' and board[d] == board[c]:
                cfg_map[d] = cfg_map[c]
            else:
                cfg_map[d] = cfg_map[c] + 1
            if cfg_before < 0 or cfg_before > cfg_map[d]:
                fringe.append(d)
    return cfg_map


def line_height(c):
    """ Return the line number above nearest board edge """
    row, col = divmod(c - (W+1), W)
    return min(row, col, N-1-row, N-1-col)


def empty_area(board, c, dist=3):
    """ Check whether there are any stones in Manhattan distance up
    to dist """
    for d in neighbors(c):
        if board[d] in 'Xx':
            return False
        elif board[d] == '.' and dist > 1 and not empty_area(board, d, dist-1):
            return False
    return True


# 3x3 pattern routines (those patterns stored in pat3src above)

def pat3_expand(pat):
    """ All possible neighborhood configurations matching a given pattern;
    used just for a combinatoric explosion when loading them in an
    in-memory set. """
    def pat_rot90(p):
        return [p[2][0] + p[1][0] + p[0][0], p[2][1] + p[1][1] + p[0][1], p[2][2] + p[1][2] + p[0][2]]
    def pat_vertflip(p):
        return [p[2], p[1], p[0]]
    def pat_horizflip(p):
        return [l[::-1] for l in p]
    def pat_swapcolors(p):
        return [l.replace('X', 'Z').replace('x', 'z').replace('O', 'X').replace('o', 'x').replace('Z', 'O').replace('z', 'o') for l in p]
    def pat_wildexp(p, c, to):
        i = p.find(c)
        if i == -1:
            return [p]
        return reduce(lambda a, b: a + b, [pat_wildexp(p[:i] + t + p[i+1:], c, to) for t in to])
    def pat_wildcards(pat):
        return [p for p in pat_wildexp(pat, '?', list('.XO '))
                  for p in pat_wildexp(p, 'x', list('.O '))
                  for p in pat_wildexp(p, 'o', list('.X '))]
    return [p for p in [pat, pat_rot90(pat)]
              for p in [p, pat_vertflip(p)]
              for p in [p, pat_horizflip(p)]
              for p in [p, pat_swapcolors(p)]
              for p in pat_wildcards(''.join(p))]

pat3set = set([p.replace('O', 'x') for p in pat3src for p in pat3_expand(p)])

def neighborhood_33(board, c):
    """ return a string containing the 9 points forming 3x3 square around
    a certain move candidate """
    return (board[c-W-1 : c-W+2] + board[c-1 : c+2] + board[c+W-1 : c+W+2]).replace('\n', ' ')


# large-scale pattern routines (those patterns living in patterns.{spat,prob} files)

# are you curious how these patterns look in practice? get
# https://github.com/pasky/pachi/blob/master/tools/pattern_spatial_show.pl
# and try e.g. ./pattern_spatial_show.pl 71

spat_patterndict = dict()  # hash(neighborhood_gridcular()) -> spatial id
def load_spat_patterndict(f):
    """ load dictionary of positions, translating them to numeric ids """
    for line in f:
        # line: 71 6 ..X.X..OO.O..........#X...... 33408f5e 188e9d3e 2166befe aa8ac9e 127e583e 1282462e 5e3d7fe 51fc9ee
        if line.startswith('#'):
            continue
        neighborhood = line.split()[2].replace('#', ' ').replace('O', 'x')
        spat_patterndict[hash(neighborhood)] = int(line.split()[0])

large_patterns = dict()  # spatial id -> probability
def load_large_patterns(f):
    """ dictionary of numeric pattern ids, translating them to probabilities
    that a move matching such move will be played when it is available """
    # The pattern file contains other features like capture, selfatari too;
    # we ignore them for now
    for line in f:
        # line: 0.004 14 3842 (capture:17 border:0 s:784)
        p = float(line.split()[0])
        m = re.search('s:(\d+)', line)
        if m is not None:
            s = int(m.groups()[0])
            large_patterns[s] = p


def neighborhood_gridcular(board, c):
    """ Yield progressively wider-diameter gridcular board neighborhood
    stone configuration strings, in all possible rotations """
    # Each rotations element is (xyindex, xymultiplier)
    rotations = [((0,1),(1,1)), ((0,1),(-1,1)), ((0,1),(1,-1)), ((0,1),(-1,-1)),
                 ((1,0),(1,1)), ((1,0),(-1,1)), ((1,0),(1,-1)), ((1,0),(-1,-1))]
    neighborhood = ['' for i in range(len(rotations))]
    wboard = board.replace('\n', ' ')
    for dseq in pat_gridcular_seq:
        for ri in range(len(rotations)):
            r = rotations[ri]
            for o in dseq:
                y, x = divmod(c - (W+1), W)
                y += o[r[0][0]]*r[1][0]
                x += o[r[0][1]]*r[1][1]
                if y >= 0 and y < N and x >= 0 and x < N:
                    neighborhood[ri] += wboard[(y+1)*W + x+1]
                else:
                    neighborhood[ri] += ' '
            yield neighborhood[ri]


def large_pattern_probability(board, c):
    """ return probability of large-scale pattern at coordinate c.
    Multiple progressively wider patterns may match a single coordinate,
    we consider the largest one. """
    probability = None
    matched_len = 0
    non_matched_len = 0
    for n in neighborhood_gridcular(board, c):
        sp_i = spat_patterndict.get(hash(n))
        prob = large_patterns.get(sp_i) if sp_i is not None else None
        if prob is not None:
            probability = prob
            matched_len = len(n)
        elif matched_len < non_matched_len < len(n):
            # stop when we did not match any pattern with a certain
            # diameter - it ain't going to get any better!
            break
        else:
            non_matched_len = len(n)
    return probability


###########################
# montecarlo playout policy

# yeild: return at yeild, and continue at same place
# capture or pat3 just consider in the heuristic_set, which is last_moves_neighbors in this case
# prob[captrue]: the probility to consider a capture first
# prob[pat3]: the probility to consider a 3x3 pattern second
# others, find a move starting with a random point
def gen_playout_moves(pos, heuristic_set, probs={'capture': 1, 'pat3': 1}, expensive_ok=False):
    """ Yield candidate next moves in the order of preference; this is one
    of the main places where heuristics dwell, try adding more!

    heuristic_set is the set of coordinates considered for applying heuristics;
    this is the immediate neighborhood of last two moves in the playout, but
    the whole board while prioring the tree. """

    # Check whether any local group is in atari and fill that liberty
    # print('local moves', [str_coord(c) for c in heuristic_set], file=sys.stderr)
    if random.random() <= probs['capture']:
        already_suggested = set()
        for c in heuristic_set:
            if pos.board[c] in 'Xx':
                in_atari, ds = fix_atari(pos, c, twolib_edgeonly=not expensive_ok)
                random.shuffle(ds)
                for d in ds:
                    if d not in already_suggested:
                        yield (d, 'capture '+str(c))
                        already_suggested.add(d)

    # Try to apply a 3x3 pattern on the local neighborhood
    if random.random() <= probs['pat3']:
        already_suggested = set()
        for c in heuristic_set:
            if pos.board[c] == '.' and c not in already_suggested and neighborhood_33(pos.board, c) in pat3set:
                yield (c, 'pat3')
                already_suggested.add(c)

    # Try *all* available moves, but starting from a random point
    # (in other words, suggest a random move)
    x, y = random.randint(1, N), random.randint(1, N)
    for c in pos.moves(y*W + x):
        yield (c, 'random')

# disp: used for tsdebug, seems like useless for us
# Method: for a given position, play the game until end (two pass or max_len)
# for each play, generate a list and try to play at 1st coord, if self-atari,go next
# if cannot find a move, then pass
# after end, use pos.score to calculate the score and return it. 
def mcplayout(pos, disp=False):
    """ Start a Monte Carlo playout from a given position,
    return score for to-play player at the starting position;
    """
    #print("Mcplayout Simulating...")
    if disp:  print('** SIMULATION **', file=sys.stderr)
    start_n = pos.n
    passes = 0
    while passes < 2 and pos.n < MAX_GAME_LEN:
        if disp:  print_pos(pos)

        pos2 = None
        # We simply try the moves our heuristics generate, in a particular
        # order, but not with 100% probability; this is on the border between
        # "rule-based playouts" and "probability distribution playouts".
        for c, kind in gen_playout_moves(pos, pos.last_moves_neighbors(), PROB_HEURISTIC):
            if disp and kind != 'random':
                print('move suggestion', str_coord(c), kind, file=sys.stderr)
            pos2 = pos.move(c)
            if pos2 is None:
                continue
            # check if the suggested move did not turn out to be a self-atari
            if random.random() <= (PROB_RSAREJECT if kind == 'random' else PROB_SSAREJECT):
                in_atari, ds = fix_atari(pos2, c, singlept_ok=True, twolib_edgeonly=True)
                if ds:
                    if disp:  print('rejecting self-atari move', str_coord(c), file=sys.stderr)
                    pos2 = None
                    continue
            break
        if pos2 is None:  # no valid moves, pass
            pos = pos.pass_move()
            passes += 1
            continue
        passes = 0
        pos = pos2

    owner_map = W*W*[0]
    score = pos.score(owner_map)
    if disp:  print('** SCORE B%+.1f **' % (score if pos.n % 2 == 0 else -score), file=sys.stderr)
    if start_n % 2 != pos.n % 2:
        score = -score
    #print("Mcplayout Simlating Done.")
    return score, owner_map


########################
# montecarlo tree search

class TreeNode():
    """ Monte-Carlo tree node;
    v is #visits, w is #wins for to-play (expected reward is w/v)
    pv, pw are prior values (node value = w/v + pw/pv)
    av, aw are amaf values ("all moves as first", used for the RAVE tree policy)
    children is None for leaf nodes """
    def __init__(self, pos):
        self.pos = pos
        self.v = 0
        self.w = 0
        self.pv = PRIOR_EVEN
        self.pw = PRIOR_EVEN/2
        self.children = None
        self.select = 0
        self.possibility = None
        self.change = False
        self.possi = 0

    # set all the possible moves to be children
    def expand(self):
        """ add and initialize children to a leaf node """
        cfg_map = cfg_distances(self.pos.board, self.pos.last) if self.pos.last is not None else None
        self.children = []
        childset = dict()
        # Use playout generator to generate children and initialize them
        # with some priors to bias search towards more sensible moves.
        # Note that there can be many ways to incorporate the priors in
        # next node selection (progressive bias, progressive widening, ...).

        #set every gen_playout_moves to be child
        for c, kind in gen_playout_moves(self.pos, range(N, (N+1)*W), expensive_ok=True):
            pos2 = self.pos.move(c)
            if pos2 is None:
                continue
            # gen_playout_moves() will generate duplicate suggestions
            # if a move is yielded by multiple heuristics
            try:
                node = childset[pos2.last]
            except KeyError:
                node = TreeNode(pos2)
                self.children.append(node)
                childset[pos2.last] = node

            if kind.startswith('capture'):
                # Check how big group we are capturing; coord of the group is
                # second word in the ``kind`` string
                if floodfill(self.pos.board, int(kind.split()[1])).count('#') > 1:
                    node.pv += PRIOR_CAPTURE_MANY
                    node.pw += PRIOR_CAPTURE_MANY
                else:
                    node.pv += PRIOR_CAPTURE_ONE
                    node.pw += PRIOR_CAPTURE_ONE
            elif kind == 'pat3':
                node.pv += PRIOR_PAT3
                node.pw += PRIOR_PAT3

        # Second pass setting priors, considering each move just once now
        for node in self.children:
            c = node.pos.last

            if cfg_map is not None and cfg_map[c]-1 < len(PRIOR_CFG):
                node.pv += PRIOR_CFG[cfg_map[c]-1]
                node.pw += PRIOR_CFG[cfg_map[c]-1]

            height = line_height(c)  # 0-indexed
            if height <= 2 and empty_area(self.pos.board, c):
                # No stones around; negative prior for 1st + 2nd line, positive
                # for 3rd line; sanitizes opening and invasions
                if height <= 1:
                    node.pv += PRIOR_EMPTYAREA
                    node.pw += 0
                if height == 2:
                    node.pv += PRIOR_EMPTYAREA
                    node.pw += PRIOR_EMPTYAREA

            in_atari, ds = fix_atari(node.pos, c, singlept_ok=True)
            if ds:
                node.pv += PRIOR_SELFATARI
                node.pw += 0  # negative prior

            patternprob = large_pattern_probability(self.pos.board, c)
            if patternprob is not None and patternprob > 0.001:
                pattern_prior = math.sqrt(patternprob)  # tone up
                node.pv += pattern_prior * PRIOR_LARGEPATTERN
                node.pw += pattern_prior * PRIOR_LARGEPATTERN

        if not self.children:
            # No possible moves, add a pass move
            self.children.append(TreeNode(self.pos.pass_move()))

    def selection(self, total_sim=0, possibility=None):
        v = self.v + self.pv
        expectation = float(self.w+self.pw) / v
        if possibility is None:
            self.select = expectation
            return expectation
        possi = possibility[self.pos.last] if self.pos.last is not None else possibility[0]
        if total_sim==0:
            self.select = expectation + CPUCT*possi
            return expectation + CPUCT*possi
        else:
            self.select = expectation + CPUCT*possi*np.sqrt(total_sim)/(1+self.v)
            return expectation + CPUCT*possi*np.sqrt(total_sim)/(1+self.v)

    def winrate(self):
        return float(self.w) / self.v if self.v > 0 else float('nan')

    def best_move(self):
        """ best move is the most simulated one """
        return max(self.children, key=lambda node: node.v) if self.children is not None else None


def tree_dcnn(tree):
    possibility = DCNN.dcnn(tree.pos, model)
    if tree.children is None:
        tree.expand()
    for child in tree.children:
        child.possi = possibility[child.pos.last] if child.pos.last is not None else possibility[0]
    return max(tree.children, key=lambda node: node.possi)

###################
# user interface(s)

# utility routines

def print_pos(pos, f=sys.stderr, owner_map=None):
    """ print visualization of the given board position, optionally also
    including an owner map statistic (probability of that area of board
    eventually becoming black/white) """
    if pos.n % 2 == 0:  # to-play is black
        board = pos.board.replace('x', 'O')
        Xcap, Ocap = pos.cap
    else:  # to-play is white
        board = pos.board.replace('X', 'O').replace('x', 'X')
        Ocap, Xcap = pos.cap
    print('Move: %-3d   Black: %d caps   White: %d caps  Komi: %.1f' % (pos.n, Xcap, Ocap, pos.komi), file=f)
    pretty_board = ' '.join(board.rstrip()) + ' '
    if pos.last is not None:
        pretty_board = pretty_board[:pos.last*2-1] + '(' + board[pos.last] + ')' + pretty_board[pos.last*2+2:]
    rowcounter = count()
    pretty_board = [' %-02d%s' % (N-i, row[2:]) for row, i in zip(pretty_board.split("\n")[1:], rowcounter)]
    if owner_map is not None:
        pretty_ownermap = ''
        for c in range(W*W):
            if board[c].isspace():
                pretty_ownermap += board[c]
            elif owner_map[c] > 0.6:
                pretty_ownermap += 'X'
            elif owner_map[c] > 0.3:
                pretty_ownermap += 'x'
            elif owner_map[c] < -0.6:
                pretty_ownermap += 'O'
            elif owner_map[c] < -0.3:
                pretty_ownermap += 'o'
            else:
                pretty_ownermap += '.'
        pretty_ownermap = ' '.join(pretty_ownermap.rstrip())
        pretty_board = ['%s   %s' % (brow, orow[2:]) for brow, orow in zip(pretty_board, pretty_ownermap.split("\n")[1:])]
    print("\n".join(pretty_board), file=f)
    print('    ' + ' '.join(colstr[:N]), file=f)
    print('', file=f)


def dump_subtree(node, thres=N_SIMS/50, indent=0, f=sys.stderr, recurse=True):
    """ print this node and all its children with v >= thres. """
    print("%s+- %s %.3f (%d/%d, prior %d/%d, selection %.3f)" %
          (indent*' ', str_coord(node.pos.last), node.winrate(),
           node.w, node.v, node.pw, node.pv, node.select), file=f)
    if not recurse:
        return
    for child in sorted(node.children, key=lambda n: n.v, reverse=True):
        if child.v >= thres:
            dump_subtree(child, thres=thres, indent=indent+3, f=f)


def print_tree_summary(tree, sims, f=sys.stderr):
    best_nodes = sorted(tree.children, key=lambda n: n.v, reverse=True)[:5]
    best_seq = []
    node = tree
    while node is not None:
        best_seq.append(node.pos.last)
        node = node.best_move()
    print('[%4d] winrate %.3f | seq %s | can %s' %
          (sims, best_nodes[0].winrate(), ' '.join([str_coord(c) for c in best_seq[1:6]]),
           ' '.join(['%s(%.3f)' % (str_coord(n.pos.last), n.winrate()) for n in best_nodes])), file=f)


def parse_coord(s):
    if s == 'pass':
        return None
    return W+1 + (N - int(s[1:])) * W + colstr.index(s[0].upper())


def str_coord(c):
    if c is None:
        return 'pass'
    row, col = divmod(c - (W+1), W)
    return '%c%d' % (colstr[col], N - row)


# various main programs

def gtp_io():
    """ GTP interface for our program.  We can play only on the board size
    which is configured (N), and we ignore color information and assume
    alternating play! """
    known_commands = ['boardsize', 'clear_board', 'komi', 'play', 'genmove',
                      'final_score', 'quit', 'name', 'version', 'known_command',
                      'list_commands', 'protocol_version']

    tree = TreeNode(pos=empty_position())
    tree.expand()

    while True:
        try:
            line = input().strip()
        except EOFError:
            break
        if line == '':
            continue
        command = [s.lower() for s in line.split()]
        if re.match('\d+', command[0]):
            cmdid = command[0]
            command = command[1:]
        else:
            cmdid = ''
        owner_map = W*W*[0]
        ret = ''
        #cannot change boardsize, unless change N
        if command[0] == "boardsize":
            if int(command[1]) != N:
                print("Warning: Trying to set incompatible boardsize %s (!= %d)" % (command[1], N), file=sys.stderr)
                ret = None
        elif command[0] == "clear_board":
            tree = TreeNode(pos=empty_position())
            tree.expand()
        elif command[0] == "komi":
            # XXX: can we do this nicer?!
            tree.pos = Position(board=tree.pos.board, cap=(tree.pos.cap[0], tree.pos.cap[1]),
                                n=tree.pos.n, ko=tree.pos.ko, last=tree.pos.last, last2=tree.pos.last2,
                                komi=float(command[1]))
        #do not response to color, just b-w-b-w-b-w...
        elif command[0] == "play":
            c = parse_coord(command[2])
            if c is not None:
                # Find the next node in the game tree and proceed there
                if tree.children is not None and filter(lambda n: n.pos.last == c, tree.children):
                    tree = filter(lambda n: n.pos.last == c, tree.children).__next__()
                else:
                    # Several play commands in row, eye-filling move, etc.
                    tree = TreeNode(pos=tree.pos.move(c))

            else:
                # Pass move
                if tree.children[0].pos.last is None:
                    tree = tree.children[0]
                else:
                    tree = TreeNode(pos=tree.pos.pass_move())
        elif command[0] == "genmove":
            #tree = tree_search(tree, N_SIMS, owner_map)
            tree = tree_dcnn(tree)
            if tree.pos.last is None:
                ret = 'pass'
            else:
                ret = str_coord(tree.pos.last)
        elif command[0] == "final_score":
            score = tree.pos.score()
            if tree.pos.n % 2:
                score = -score
            if score == 0:
                ret = '0'
            elif score > 0:
                ret = 'B+%.1f' % (score,)
            elif score < 0:
                ret = 'W+%.1f' % (-score,)
        elif command[0] == "name":
            ret = 'foolgo'
        elif command[0] == "version":
            ret = 'DCNN+MCTS demo'
        elif command[0] == "list_commands":
            ret = '\n'.join(known_commands)
        elif command[0] == "known_command":
            ret = 'true' if command[1] in known_commands else 'false'
        elif command[0] == "protocol_version":
            ret = '2'
        elif command[0] == "quit":
            print('=%s \n\n' % (cmdid,), end='')
            break
        else:
            print('Warning: Ignoring unknown command - %s' % (line,), file=sys.stderr)
            ret = None

        #print_pos(tree.pos, sys.stderr, owner_map)
        if ret is not None:
            print('=%s %s\n\n' % (cmdid, ret,), end='')
        else:
            print('?%s ???\n\n' % (cmdid,), end='')
        sys.stdout.flush()

if __name__ == "__main__":
    try:
        print("Loading model for DCNN...", file=sys.stderr)
        model = DCNN.loadModel()
        print('Done.', file=sys.stderr)
    except IOError as e:
        print("Warning: Cannot load DCNN model, cannot run!", file=sys.stderr)

    gtp_io()
