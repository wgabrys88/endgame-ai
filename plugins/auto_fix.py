def run(board):
    if board.get("consecutive_failures",0)>2:
        board["plan"]=[]
    return None
