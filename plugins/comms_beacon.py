import json,os,time
def run(board):
    os.makedirs("runtime/comms",exist_ok=True)
    open(f"runtime/comms/beacon-{os.getpid()}.json","w").write(json.dumps({"pid":os.getpid(),"ts":time.time()}))
    return None
