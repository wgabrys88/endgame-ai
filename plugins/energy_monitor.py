def run(board):
    # Check current energy level (assuming board has an energy attribute)
    energy = board.get('energy', 100)
    print(f"[EnergyMonitor] Current energy: {energy}%")

    if energy < 20:
        print("ALERT: Low energy detected! Initiating emergency shutdown sequence.")
        # In a real scenario, this would trigger an action via the bus or API
        return {'phase': 'emergency_shutdown', 'data': f"Energy critical at {energy}%", 'action': 'initiate_shutdown'}
    else:
        print("Energy levels nominal.")
        return {'phase': 'nominal', 'data': f"Energy stable at {energy}%", 'action': 'none'}
