import numpy as np
import mxnet as mx
import time

board_size = 19
deltai = [-1, 1, 0, 0]
deltaj = [0, 0, -1, 1]

def POS(i, j):
    return i * board_size + j

def I(pos):
    return int(pos / board_size)

def J(pos):
    return pos % board_size

def onBoard(i, j):
    return i >= 0 and i < board_size and j >= 0 and j < board_size

def show(board):
    print('   ', end = '')
    for i in range(board_size):
        print('{0:>3}'.format(i), end='')
    print('', end='\n')
    for i in range(board_size):
        print('{0:>3}'.format(i), end='')
        for j in range(board_size):
            if (board[i][j] == 1):
                print('{0:>3}'.format('X'), end='')
            elif (board[i][j] == -1):
                print('{0:>3}'.format('O'), end='')
            else:
                print('{0:>3}'.format('.'), end='')
        print('')

def showLib(lib_board):
    print('   ', end = '')
    for i in range(board_size):
        print('{0:>3}'.format(i), end='')
    print('', end='\n')
    for i in range(board_size):
        print('{0:>3}'.format(i), end='')
        for j in range(board_size):
            print('{0:>3}'.format(lib_board[i][j]), end='')
        print('')

def P19toP21(pos_19):
    row = I(pos_19)
    column = J(pos_19)
    return (board_size + 2) * (row + 1) + (column + 1)

def P21toP19(pos_21):
    row = int(pos_21 / (board_size + 2)) - 1
    column = pos_21 % (board_size + 2) - 1
    return POS(row, column)

def B19toB21(board_19):
    board_441 = ' ' * 20
    board_441 = board_441 + '\n'
    for i in range(len(board_19)):
        board_441 = board_441 + ' '
        for j in range(len(board_19[i])):
            if (board_19[i][j] == 1):
                board_441 = board_441 + 'X'
            elif (board_19[i][j] == -1):
                board_441 = board_441 + 'x'
            else:
                board_441 = board_441 + '.'
        board_441 = board_441 + '\n'
    board_441 = board_441 + ' ' * 21
    return board_441

def B21toB19(board_441):
    board_19 = [[0 for i in range(board_size)] for j in range(board_size)]
    tmp = board_441.strip()
    tmp = tmp.split('\n')
    for i in range(len(tmp)):
        tmp[i] = tmp[i].strip()
        for j in range(len(tmp[i])):
            if (tmp[i][j] == 'X'):
                board_19[i][j] = 1
            elif (tmp[i][j] == 'x'):
                board_19[i][j] = -1
    return board_19

def sameString(pos1, pos2, next_stone):
    pos = pos1
    while (True):
        if (pos == pos2):
            return True
        pos = next_stone[pos]
        if (pos == pos1):
            break
    return False

def getNextStone(chessboard):
    next_stone = [i for i in range(board_size * board_size)]
    for i in range(board_size):
        for j in range(board_size):
            pos = POS(i, j)
            if (chessboard[i][j] == 0):
                next_stone[pos] = 0
                continue
            for k in range(4):
                ai = i + deltai[k]
                aj = j + deltaj[k]
                pos2 = POS(ai, aj)
                if (onBoard(ai, aj)
                    and chessboard[ai][aj] == chessboard[i][j]
                    and not sameString(pos, pos2, next_stone)):
                    next_stone[pos], next_stone[pos2] = next_stone[pos2], next_stone[pos]
    return next_stone

def liberty(i, j, chessboard, lib_board, next_stone):
    if (chessboard[i][j] == 0):
        return -1
    if (lib_board[i][j] >= 0):
        return lib_board[i][j]
    
    lib = 0
    pos = POS(i, j)
    flag = [[False for p in range(board_size)] for q in range(board_size)]
    while (True):
        ai = I(pos)
        aj = J(pos)
        for k in range(4):
            bi = ai + deltai[k]
            bj = aj + deltaj[k]
            if (onBoard(bi, bj)
                and chessboard[bi][bj] == 0
                and not flag[bi][bj]):
                flag[bi][bj] = True
                lib = lib + 1
        pos = next_stone[pos]
        if (pos == POS(i, j)):
            break
    
    pos = POS(i, j)
    while (True):
        ai = I(pos)
        aj = J(pos)
        lib_board[ai][aj] = lib
        pos = next_stone[pos]
        if (pos == POS(i, j)):
            break
    return lib

def getLIBERTY(chessboard, next_stone):
    lib_board = [[-1 for i in range(board_size)] for j in range(board_size)]
    for i in range(board_size):
        for j in range(board_size):
            lib_board[i][j] = liberty(i, j, chessboard, lib_board, next_stone)
    return lib_board

def addFeature(CHESSBOARD, LIBERTY, LAST_1, LAST_2):
    CHESSBOARD = np.array(CHESSBOARD)
    CHESSBOARD_4d = CHESSBOARD.reshape(CHESSBOARD.shape[0], 1, board_size, board_size)
    CHESSBOARD_4d = CHESSBOARD_4d.tolist()
    feature_size = 255
    for i in range(len(CHESSBOARD_4d)):
        for j in range(10):
            CHESSBOARD_4d[i].append([[0 for p in range(board_size)] for q in range(board_size)])
        # CHESSBOARD_4d in 2nd dimension presents:
        #   0 - empty
        #   1 - self
        #   2 - oppo
        #   3 - self liberty 1
        #   4 - self liberty 2
        #   5 - self liberty more than 2
        #   6 - oppo liberty 1
        #   7 - oppo liberty 2
        #   8 - oppo liberty more than 2
        #   9 - last step
        #   10- last but one step
        for p in range(board_size):
            for q in range(board_size):
                if (CHESSBOARD[i][p][q] == 1): # self
                    CHESSBOARD_4d[i][0][p][q] = 0 # empty
                    CHESSBOARD_4d[i][1][p][q] = feature_size # self
                    if (LIBERTY[i][p][q] == 1): # liberty 1
                        CHESSBOARD_4d[i][3][p][q] = feature_size
                    elif (LIBERTY[i][p][q] == 2): # liberty 2
                        CHESSBOARD_4d[i][4][p][q] = feature_size
                    elif (LIBERTY[i][p][q] > 2): # liberty more than 2
                        CHESSBOARD_4d[i][5][p][q] = feature_size
                elif (CHESSBOARD[i][p][q] == -1): # oppo
                    CHESSBOARD_4d[i][0][p][q] = 0 # empty
                    CHESSBOARD_4d[i][2][p][q] = feature_size # oppo
                    if (LIBERTY[i][p][q] == 1): # liberty 1
                        CHESSBOARD_4d[i][6][p][q] = feature_size
                    elif (LIBERTY[i][p][q] == 2): # liberty 2
                        CHESSBOARD_4d[i][7][p][q] = feature_size
                    elif (LIBERTY[i][p][q] > 2): # liberty more than 2
                        CHESSBOARD_4d[i][8][p][q] = feature_size
                else:
                    CHESSBOARD_4d[i][0][p][q] = feature_size # empty

                if (POS(p, q) == LAST_1[i]):
                    CHESSBOARD_4d[i][9][p][q] = feature_size # last step
                if (POS(p, q) == LAST_2[i]):
                    CHESSBOARD_4d[i][10][p][q] = feature_size # last but one step
    return CHESSBOARD_4d

def loadModel():
    prefix = 'dcnnGoModel'
    iteration = 10
    model = mx.model.FeedForward.load(prefix, iteration)
    return model

def dcnn(argPOS, model):
    CHESSBOARD = [] #1 for itself, -1 for enemy
    LIBERTY = []
    LAST_1 = []
    LAST_2 = []
    next_stone = []

    CHESSBOARD.append(B21toB19(argPOS.board))
    next_stone = getNextStone(CHESSBOARD[0])
    LIBERTY.append(getLIBERTY(CHESSBOARD[0], next_stone))
    if (argPOS.last == None):
        LAST_1.append(-1)
    else:
        LAST_1.append(P21toP19(argPOS.last))
    if (argPOS.last2 == None):
        LAST_2.append(-1)
    else:
        LAST_2.append(P21toP19(argPOS.last2))

    val_CHESSBOARD = np.array(addFeature(CHESSBOARD, LIBERTY, LAST_1, LAST_2)).astype(np.float32)    prob = model.predict(val_CHESSBOARD[0:1])[0]
    prob_21 = [0 for i in range((board_size + 2) * (board_size + 2))]
    for i in range(board_size * board_size):
        prob_21[P19toP21(i)] = prob[i]
    
    return prob_21


