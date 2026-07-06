# wiring.json: The Immutable Circuit

`wiring.json` is not configuration. It is **the organism's DNA** — a single JSON file that defines the complete topology, transports, prompts, and self-modification rules. The organism never rewires itself mid-run; `node_self_modify` proposes patches, the local body validates (Python compile + JSON parse), commits, and optionally pushes.

```mermaid
stateDiagram-v2
    [*] --> node_planner
    node_planner --> node_scheduler : step_ready
    node_planner --> node_reflect : reflect
    node_planner --> node_error : error
    node_scheduler --> node_observe : step_ready
    node_scheduler --> node_satisfied : plan_complete
    node_scheduler --> node_error : error
    node_observe --> node_planner : initial_screen
    node_observe --> node_execute : screen_ready
    node_observe --> node_error : error
    node_execute --> node_verify : verify
    node_execute --> node_frame_action : frame
    node_execute --> node_reflect : reflect
    node_execute --> node_self_modify : self_modify
    node_execute --> node_error : error
    node_verify --> node_scheduler : step_confirmed
    node_verify --> node_reflect : step_denied
    node_verify --> node_error : error
    node_reflect --> node_observe : retry
    node_reflect --> node_planner : replan
    node_reflect --> node_frame_action : frame
    node_reflect --> node_self_modify : escalate
    node_reflect --> node_satisfied : give_up
    node_reflect --> node_error : error
    node_self_modify --> node_planner : modified
    node_self_modify --> node_reflect : modify_failed
    node_self_modify --> node_error : error
    node_satisfied --> [*] : halt
    node_frame_action --> node_execute : framed
    node_frame_action --> node_reflect : reflect
    node_frame_action --> node_error : error
    node_error --> node_planner : planner
    node_error --> node_reflect : reflect
    node_error --> [*] : halt
```

## Transport Layer (Pluggable Brains)

```json
"model": {
  "transport": "transport_xai",
  "transport_config": {
    "transport_xai": {
      "mode": "api",
      "api_key_env": "XAI_API_KEY",
      "model": "grok-4.3",
      "reasoning": { "enabled": true, "effort": "low" }
    },
    "transport_file_proxy": {
      "request_path": "runtime_request.json",
      "response_path": "runtime_response.json"
    },
    "transport_openai": { "base_url": "http://localhost:1234", "model": "nemotron-3-nano-4b" },
    "transport_opencode": { "executable": "opencode-cli.exe" }
  }
}
```

Switching brains = changing one string. The organism doesn't care.