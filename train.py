import os
import shutil
import numpy as np
import mxnet as mx
import matplotlib.pyplot as plt
import std
import play

board_size = 19

if __name__ == '__main__':
    train_path = 'sgf'
    # train_path = 'sgf_beta'
    done_path = 'sgf_done'
    test_path = 'test'
    
    # construct symbol
    data = mx.symbol.Variable('data')
    # 1st conv layer
    conv1 = mx.symbol.Convolution(data=data, kernel=(5,5), num_filter=92)
    tanh1 = mx.symbol.Activation(data=conv1, act_type="tanh")
    # 2nd conv layer
    conv2 = mx.symbol.Convolution(data=tanh1, kernel=(3,3), num_filter=384)
    tanh2 = mx.symbol.Activation(data=conv2, act_type="tanh")
    # 3rd conv layer
    conv3 = mx.symbol.Convolution(data=tanh2, kernel=(3,3), num_filter=384)
    tanh3 = mx.symbol.Activation(data=conv3, act_type="tanh")
    # 4th conv layer
    conv4 = mx.symbol.Convolution(data=tanh3, kernel=(3,3), num_filter=384)
    tanh4 = mx.symbol.Activation(data=conv4, act_type="tanh")
    # 1st fullc layer
    flatten = mx.symbol.Flatten(data=tanh4)
    fc1 = mx.symbol.FullyConnected(data=flatten, num_hidden=724)
    tanh5 = mx.symbol.Activation(data=fc1, act_type="tanh")
    # 2nd fullc layer
    fc2 = mx.symbol.FullyConnected(data=tanh5, num_hidden=362)
    # softmax loss
    lenet = mx.symbol.SoftmaxOutput(data=fc2, name='softmax')

    import logging
    logging.getLogger().setLevel(logging.DEBUG)

    # construct model
    prefix = 'dcnnGoModel'
    iteration = 10
    try:
        model = mx.model.FeedForward.load(prefix, iteration, ctx = mx.gpu(0))
    except Exception as e:
        print(e)
        model = mx.model.FeedForward(ctx = mx.gpu(0), # use GPU 0 for training, others are same as before
                                     symbol = lenet,
                                     num_epoch = iteration)
    print(model)

    # read the 'sgf' folder and get the chessboards for training
    for dirpath, dirnames, filenames in os.walk(train_path):
        print(dirpath)
        CHESSBOARD = [] #1 for itself, -1 for enemy
        OP = []
        LIBERTY = []
        LAST_1 = []
        LSAT_2 = []
        
        # get the chessboard for train
        if (len(filenames) != 0):
            CHESSBOARD, OP, LIBERTY, LAST_1, LAST_2 = play.getCHESSBOARD(dirpath)

        if (len(CHESSBOARD) == 0):
            continue
        if (len(CHESSBOARD) != len(OP)):
            print('Data error #2')
            exit()
        
        # construct train set
        train_CHESSBOARD = np.array(std.addFeature(CHESSBOARD, LIBERTY, LAST_1, LAST_2)).astype(np.float32)
        train_OP = np.array(OP)
        # release memory
        del CHESSBOARD[:]
        del OP[:]
        del LIBERTY[:]
        del LAST_1[:]
        del LAST_2[:]
        
        # get the chessboard for test
        CHESSBOARD, OP, LIBERTY, LAST_1, LAST_2 = play.getCHESSBOARD(test_path)
        
        if (len(CHESSBOARD) == 0 or len(CHESSBOARD) != len(OP)):
            print('Data error #2')
            exit()
        
        # construct test set
        val_CHESSBOARD = np.array(std.addFeature(CHESSBOARD, LIBERTY, LAST_1, LAST_2)).astype(np.float32)
        val_OP = np.array(OP)
        # release memory
        del CHESSBOARD[:]
        del OP[:]
        del LIBERTY[:]
        del LAST_1[:]
        del LAST_2[:]
        
        # train
        # batch_size must be smaller than the size of val_OP
        batch_size = 100
        train_iter = mx.io.NDArrayIter(train_CHESSBOARD, train_OP, batch_size, shuffle=True)
        val_iter = mx.io.NDArrayIter(val_CHESSBOARD, val_OP, batch_size)
        
        model.fit(
            X=train_iter,  
            eval_data=val_iter, 
            batch_end_callback = mx.callback.Speedometer(batch_size, 5)
        )

        # save model
        model.save(prefix)
        print(dirpath, 'training completed\n')
        f = open('log.txt', 'a')
        f.write(dirpath + '\n')
        f.close()
        shutil.move(dirpath, done_path)

        
