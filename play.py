import os
import copy
import std

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

def hasAdditionalLiberty(i, j, libi, libj, chessboard, next_stone):
    pos = POS(i, j)
    while (True):
        ai = I(pos)
        aj = J(pos)
        for k in range(4):
            bi = ai + deltai[k]
            bj = aj + deltaj[k]
            if (onBoard(bi, bj)
                and chessboard[bi][bj] == 0
                and (bi != libi or bj != libj)):
                return True;
        pos = next_stone[pos];
        if (pos == POS(i, j)):
            break
    return False

def removeString(i, j, chessboard_1, chessboard_2, next_stone):
    pos = POS(i, j)
    while (True):
        ai = I(pos)
        aj = J(pos)
        chessboard_1[ai][aj] = 0
        chessboard_2[ai][aj] = 0
        pos = next_stone[pos];
        if (pos == POS(i, j)):
            break

def sameString(pos1, pos2, next_stone):
    pos = pos1
    while (True):
        if (pos == pos2):
            return True
        pos = next_stone[pos]
        if (pos == pos1):
            break
    return False

def playMove(i, j, chessboard_1, chessboard_2, next_stone):
    pos = POS(i, j)
    for k in range(4):
        ai = i + deltai[k]
        aj = j + deltaj[k]
        if (onBoard(ai, aj)
            and chessboard_1[ai][aj] + chessboard_1[i][j] == 0
            and not hasAdditionalLiberty(ai, aj, i, j, chessboard_1, next_stone)):
            removeString(ai, aj, chessboard_1, chessboard_2, next_stone)

    next_stone[pos] = pos
    for k in range(4):
        ai = i + deltai[k]
        aj = j + deltaj[k]
        pos2 = POS(ai, aj)
        if (onBoard(ai, aj)
            and chessboard_1[ai][aj] == chessboard_1[i][j]
            and not sameString(pos, pos2, next_stone)):
            next_stone[pos], next_stone[pos2] = next_stone[pos2], next_stone[pos]

    lib_board = [[-1 for p in range(board_size)] for q in range(board_size)]
    for p in range(board_size):
        for q in range(board_size):
            lib_board[p][q] = liberty(p, q, chessboard_1, lib_board, next_stone)
    return lib_board

def getCHESSBOARD(path):
    filenames = os.listdir(path)
    CHESSBOARD = [] #1 for itself, -1 for enemy
    OP = []
    LIBERTY = []
    LAST_1 = []
    LAST_2 = []
    for filename in filenames:
        print(os.path.join(path, filename))
        try:
            file = open(os.path.join(path, filename))
            string = file.read()
            string = string.replace('(', '')
            string = string.replace(')', '')
            array = string.split(';')
            file.close()
        except:
            print('File error.')
            continue
        
        next_stone = [0 for i in range(board_size * board_size)]
        lib_board = [[-1 for p in range(board_size)] for q in range(board_size)]
        chessboard_b = [[0 for p in range(board_size)] for q in range(board_size)]
        chessboard_w = [[0 for p in range(board_size)] for q in range(board_size)]
        CHESSBOARD.append(copy.deepcopy(chessboard_b))
        LIBERTY.append(copy.deepcopy(lib_board))
        LAST_1.append(-1)
        LAST_2.append(-1)
        
        try:
            if (array[1].find('AB') > 0 or array[1].find('AW') > 0 or array[2][0] != 'B'):
                print('Handicap Go')
                continue
            end_num = len(array)
            for i in range(2, end_num):
                op = array[i].strip()
                # print(op, 'No.' + str(i - 1))
                assert op[0] == 'B' or op[0] == 'W'
                
                if (op[2:4] == 'tt' or op[1:3] == '[]'):
                    OP.append(361)
                    if (op[0] == 'B'):
                        CHESSBOARD.append(copy.deepcopy(chessboard_w))
                    else:
                        CHESSBOARD.append(copy.deepcopy(chessboard_b))
                    LIBERTY.append(copy.deepcopy(lib_board))
                    LAST_2.append(LAST_1[-1])
                    LAST_1.append(OP[-1])
                else:
                    column = ord(op[2]) - ord('a')
                    row = ord(op[3]) - ord('a')
                    assert row >= 0 and row <19 and column >=0 and column < 19

                    if (CHESSBOARD[-1][row][column] != 0):
                        del CHESSBOARD[-1]
                        del LIBERTY[-1]
                        del LAST_1[-1]
                        del LAST_2[-1]
                        break

                    OP.append(POS(row, column))
                    if (i != end_num - 1):
                        if (op[0] == 'B'):
                            chessboard_b[row][column] = 1
                            chessboard_w[row][column] = -1
                            lib_board = playMove(row, column, chessboard_b, chessboard_w, next_stone)
                            CHESSBOARD.append(copy.deepcopy(chessboard_w))
                        else:
                            chessboard_w[row][column] = 1
                            chessboard_b[row][column] = -1
                            lib_board = playMove(row, column, chessboard_b, chessboard_w, next_stone)
                            CHESSBOARD.append(copy.deepcopy(chessboard_b))
                        LIBERTY.append(copy.deepcopy(lib_board))
                        LAST_2.append(LAST_1[-1])
                        LAST_1.append(OP[-1])
        except Exception as e:
            print(e)
            print('Data error #1')
        finally:
            if (len(CHESSBOARD) != len(OP)):
                del CHESSBOARD[-1]
                del LIBERTY[-1]
                del LAST_1[-1]
                del LAST_2[-1]
    
    return CHESSBOARD, OP, LIBERTY, LAST_1, LAST_2


