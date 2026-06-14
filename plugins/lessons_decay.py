def run(board):
    if board.get('progress', '').strip():
        return {'phase': 'progress_written'}
    return None
