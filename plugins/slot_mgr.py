import glob,os
def run(board):
    dead=[f for f in glob.glob("events-child-*.jsonl") if os.path.getsize(f)<50]
    board["dead_slots"]=len(dead)
    return None
