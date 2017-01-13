import numpy as np
import mxnet as mx
import matplotlib.pyplot as plt
import std
import play

board_size = 19
CHESSBOARD = [] #1 for itself, -1 for enemy
OP = []
LIBERTY = []
LAST_1 = []
LAST_2 = []

if __name__ == '__main__':
    path = 'test'
    # path = 'test_beta'
    # get the chessboard for test
    CHESSBOARD, OP, LIBERTY, LAST_1, LAST_2 = play.getCHESSBOARD(path)
    
    if (len(CHESSBOARD) == 0 or len(CHESSBOARD) != len(OP)):
        print('Data error #2')
        exit()
    
    # construct test set
    val_CHESSBOARD = np.array(std.addFeature(CHESSBOARD, LIBERTY, LAST_1, LAST_2)).astype(np.float32)
    val_OP = np.array(OP)

    prefix = 'dcnnGoModel'
    iteration = 10
    model = mx.model.FeedForward.load(prefix, iteration)
    while (True):
        print('Test set size:', val_OP.shape[0])
        while (True):
            try:
                test_num = int(input('Please input test number:'))
                if (test_num >= 0 and test_num < val_OP.shape[0]):
                    break
                print('invalid input number in 0-' + str(val_OP.shape[0] - 1))
            except Exception as e:
                print(e)

        std.show(CHESSBOARD[test_num])
        std.showLib(LIBERTY[test_num])
        if (LAST_1[test_num] == -1):
            print('[-1]')
        else:
            print('[', std.I(LAST_1[test_num]), ',', std.J(LAST_1[test_num]), ']')
        if (LAST_2[test_num] == -1):
            print('[-1]')
        else:
            print('[', std.I(LAST_2[test_num]), ',', std.J(LAST_2[test_num]), ']')
        
        prob = model.predict(val_CHESSBOARD[test_num:test_num + 1])[0]
        first_num = 10
        prob_out = prob.copy()
        for i in range(first_num):
            print('Classified as {0} [{1},{2}] with probability {3:.6}'.format(prob_out.argmax(), std.I(prob_out.argmax()), std.J(prob_out.argmax()), max(prob_out)))
            prob_out[prob_out.argmax()] = 0
        print('val_OP: {0} [{1},{2}]'.format(val_OP[test_num], std.I(val_OP[test_num]), std.J(val_OP[test_num])))


        
