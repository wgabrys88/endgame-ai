def run(board):
    if board.get("consecutive_failures",0)>=3:
        board["plan"]=[]
    return None
