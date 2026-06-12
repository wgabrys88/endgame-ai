def run(board):
    if board.get("stagnation",0)>0.8:
        board["stagnation"]=0.4
    return None
