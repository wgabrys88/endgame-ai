import json,time,os
def run(board):
    if board.get("power",0)>0:
        os.makedirs("runtime/comms",exist_ok=True)
        open("runtime/comms/fission.jsonl","a").write(json.dumps({"ts":time.time(),"power":board["power"]}) + "
")
    return None