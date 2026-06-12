from comms import agent_id, post


def run(board):
    post(
        agent_id(),
        "colony",
        f"beacon stag={float(board.get('stagnation', 0)):.2f} power={float(board.get('power', 0)):.3f}",
        kind="beacon",
    )
    return None