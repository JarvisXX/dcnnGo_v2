import numpy as np

board_size = 19

def POS(i, j):
    return i * board_size + j

def I(pos):
    return int(pos / board_size)

def J(pos):
    return pos % board_size

def show(board):
    print('   ', end = '')
    for i in range(board_size):
        print('{0:>3}'.format(i), end='')
    print()
    for i in range(board_size):
        print('{0:>3}'.format(i), end='')
        for j in range(board_size):
            if (board[i][j] == 1):
                print('{0:>3}'.format('X'), end='')
            elif (board[i][j] == -1):
                print('{0:>3}'.format('O'), end='')
            else:
                print('{0:>3}'.format('.'), end='')
        print()

def showLib(lib_board):
    print('   ', end = '')
    for i in range(board_size):
        print('{0:>3}'.format(i), end='')
    print()
    for i in range(board_size):
        print('{0:>3}'.format(i), end='')
        for j in range(board_size):
            print('{0:>3}'.format(lib_board[i][j]), end='')
        print()

def addFeature(CHESSBOARD, LIBERTY, LAST_1, LAST_2):
    CHESSBOARD = np.array(CHESSBOARD)
    CHESSBOARD_4d = CHESSBOARD.reshape(CHESSBOARD.shape[0], 1, board_size, board_size)
    CHESSBOARD_4d = CHESSBOARD_4d.tolist()
    feature_size = 255
    for i in range(len(CHESSBOARD_4d)):
        if (i % 100 == 0):
            print('%d / %d' % (i, len(CHESSBOARD_4d)))
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

def board2pic(board):
    pic = np.zeros((board_size, board_size), dtype = np.int)
    for i in range(board_size):
        for j in range(board_size):
            if (board[i][j] == 1):
                pic[i][j] = 255
            elif (board[i][j] == -1):
                pic[i][j] = 0
            else:
                pic[i][j] = 128
    return pic
