import datetime
from .comms_beacon import send_comm
def run(board):
    if board.state == "active":
        fission_log(board)
        audit_results = {"diagnosis": "Audit completed", "suggestion": "Provide step results", "rule": "Audit must be completed before reporting"}
        with open("audit_log.txt","a") as f:
            f.write(f"{datetime.datetime.now()}: {audit_results}\n")
    else:
        send_comm(board, "idle")
