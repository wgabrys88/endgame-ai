# Endgame-AI Operations README
- This README is the current operating handover for `C:\Users\px-wjt\Downloads\endgame-ai`.
- Branch at handover time: `codex/self-referential-relay`.
- Date of this status writeup: 2026-06-25.
- Endgame-AI is a local Windows desktop ROD graph operator, not a normal chatbot.
- The intended product is a real desktop control loop that can pursue user goals through observe, reason, decide, act, verify, and recover.
- The main proof target is a transparent intelligence backend switch across LM Studio, coding-agent file proxy, and browser AI relay.
- The current implementation has the queue split, per-slot model config support, relay status APIs, panel visibility, and updated docs.
- The browser relay proof is not complete yet; do not claim production success for browser AI relay.
- This document describes what was done, what was observed, what remains, and what is needed before deployment.
## 02 Purpose
- The goal is to make Endgame-AI operate the local Windows desktop through its own runtime paths.
- Slot 1 should accept real user goals and use the ROD graph to decide next steps.
- Slot 2 should act as a browser relay worker that controls an already-open browser chat as an external brain.
- Slot 1 should receive the external answer through `MEMORY.llm_response`.
- Slot 1 must not need to know whether the answer came from LM Studio, file proxy, or browser relay.
- Shell access is allowed for repository edits, validation, server operation, and file-proxy response writing.
- Shell access is not the proof mechanism for browser or desktop control.
- Browser and desktop interaction must pass through Endgame-AI observe and act nodes.
- The design target is local, inspectable, permission-bounded autonomy, not unbounded control.
## 03 Current Status Snapshot
- Static repository validation has passed after the relay queue split changes.
- Root server has been run as real `server.py` on `http://127.0.0.1:9077/`.
- Managed Slot 1 has been started on `http://127.0.0.1:9078/`.
- Managed Slot 2 has been started on `http://127.0.0.1:9079/`.
- Slot 1 used `prompts/model.json` and the `comms/slot1_cognition` file-proxy queue.
- Slot 2 used `prompts/model_relay.json` and the `comms/relay_cognition` file-proxy queue.
- Browser relay handoff used `comms/llm_proxy/request.json`.
- Slot 2 claimed browser relay request `slot1-1782422519826`.
- Slot 2 observed the desktop and captured a desktop tree including Chrome, but did not yet submit to Grok.
## 04 Workspace And Branch
- Workspace path: `C:\Users\px-wjt\Downloads\endgame-ai`.
- Active branch: `codex/self-referential-relay`.
- The repository worktree is the source of truth for the implementation state.
- Runtime files under `comms/`, `state.json`, and `state.slot*.json` are evidence, not source.
- The live run state can become stale after process restart.
- The current committed history should be checked before release tagging.
- Do not depend on stale chat memory to understand the system.
- Read the repository and runtime state before making operational claims.
- Keep generated runtime artifacts out of source control unless they are intentionally promoted to fixtures.
## 05 Core Invariant
- Slot 1 must be able to request stronger intelligence without leaving the ROD loop.
- Slot 2 must use Endgame-AI desktop observation and action to operate the browser.
- The browser answer must flow back through `comms/llm_proxy/response.json`.
- Slot 1 must consume the answer through memory, especially `MEMORY.llm_response`.
- The relay backend must be interchangeable with local OpenAI-compatible inference and file proxy cognition.
- A queue collision must not cause Slot 1 and Slot 2 to wait on each other forever.
- Prompt submission must never go into address, search, URL, or location bars.
- Response capture must never happen while the provider is still streaming or loading.
- Captures must reject stale text, prompt echoes, short snippets, questions, title-only text, and URL-only text.
## 06 Closed Loop Definition
- A closed loop starts with a user goal submitted to the root or Slot 1 server.
- The ROD graph plans the goal into observable subtasks.
- The observe node captures Windows UIA, rendered scope, hover scan data, and desktop tree context.
- The act node chooses declarative actions such as focus, click, write, press, hotkey, scroll, wait, and memory updates.
- The action dispatcher executes those declarative actions on the local desktop.
- The verify node confirms or denies the step from outcomes and stored evidence.
- The reflect node diagnoses failed or denied steps.
- The graph advances or retries based on explicit wiring edges.
- The loop is not complete if a human manually drives the browser outside Endgame-AI.
## 07 Implemented Queue Split
- Slot 1 cognition now defaults to `comms/slot1_cognition/request.json`.
- Slot 1 cognition responses now default to `comms/slot1_cognition/response.json`.
- Slot 1 cognition archives now default to `comms/slot1_cognition/archive`.
- Slot 2 cognition now uses `comms/relay_cognition/request.json`.
- Slot 2 cognition responses now use `comms/relay_cognition/response.json`.
- Slot 2 cognition archives now use `comms/relay_cognition/archive`.
- Browser relay handoff remains `comms/llm_proxy/request.json`.
- Browser relay response remains `comms/llm_proxy/response.json`.
- This split removes the main deadlock risk where Slot 2 could consume its own relay handoff as cognition.
## 08 Model Config Split
- `prompts/model.json` is the default model config for root and Slot 1 cognition.
- `prompts/model_relay.json` is the model config for Slot 2 relay cognition.
- `server.py` now supports `ENDGAME_MODEL` as an environment override.
- `spawn_slot_process()` sets `ENDGAME_MODEL` for Slot 2 when `prompts/model_relay.json` exists.
- Both model files can use `transport: file_proxy` for coding-agent cognition.
- Both model files can be changed to `transport: openai` for LM Studio or OpenAI-compatible local servers.
- The file-proxy path defaults are normalized by `normalize_model_config()`.
- Relative model paths are resolved against the repository root.
- The active model path is reported by health and system endpoints.
## 09 Server Changes
- `MODEL_PATH` is now derived from `ENDGAME_MODEL` or `prompts/model.json`.
- `DEFAULT_FILE_PROXY` now points to the Slot 1 cognition queue.
- `DEFAULT_RELAY_PROXY` now points to the browser relay handoff queue.
- File-proxy cognition status and browser relay status are now reported separately.
- `/system` reports the active model path and both proxy status blocks.
- `/health` reports `model_path` and `model_transport`.
- `/relay/status` reports browser relay request, response, and archive state.
- `/relay/clear` clears the browser relay handoff with explicit confirmation.
- Existing `/llm-proxy/clear` remains for cognition file-proxy clearing.
## 10 Panel Changes
- The panel now distinguishes cognition proxy status from browser relay status.
- The panel displays the active model path.
- The panel retains graph rendering and wiring audit visibility.
- The panel includes separate controls for clearing cognition proxy files.
- The panel includes separate controls for clearing browser relay files.
- The panel did not introduce new browser automation outside Endgame-AI.
- Panel desktop viewport checks passed after the implementation changes.
- Panel narrow viewport checks passed after the implementation changes.
- The panel is an operator console, not the browser-relay proof itself.
## 11 Model Files
- `prompts/model.json` was updated to point at `comms/slot1_cognition`.
- `prompts/model_relay.json` was added for Slot 2 relay cognition.
- `prompts/model_relay.json` points at `comms/relay_cognition`.
- Both configs currently use `transport: file_proxy` for this proof path.
- Both configs preserve sampling and timeout fields used by the OpenAI-compatible path.
- The default timeout remains long enough for human-serviced file-proxy runs.
- `prompts/model_relay.json` is whitelisted in `.gitignore`.
- Model configs are runtime configuration, not graph wiring.
- Model configs should stay small, explicit, and inspectable.
## 12 Documentation State
- This README replaces the earlier bootstrap-style README.
- `SETUP_AND_LAUNCH.md` has been updated for root launch and queue split operation.
- `DESIGN_RATIONALE.md` has been updated for relay design and limitations.
- Documentation must not claim browser relay success until the live proof completes.
- Documentation must not claim unlimited or unconstrained capability.
- Documentation should state account, rate limit, UI, permission, and operator-approval limits.
- Documentation should make the three intelligence backends explicit.
- Documentation should explain how Slot 1 consumes `MEMORY.llm_response`.
- Documentation should treat runtime evidence as separate from static validation.
## 13 Static Validation Completed
- JSON parse validation passed for `prompts/wiring.json`.
- JSON parse validation passed for `prompts/wiring_relay.json`.
- JSON parse validation passed for `prompts/model.json`.
- JSON parse validation passed for `prompts/model_relay.json`.
- `python -m compileall -q .` passed.
- `pyright server.py colony.py desktop.py` passed with zero errors.
- `git diff --check` passed, with only line-ending warnings expected from attributes.
- `server.wiring_audit()` passed for the main wiring.
- `server.wiring_audit()` passed for the relay wiring.
## 14 Panel Validation Completed
- Root panel returned HTTP 200 at `http://127.0.0.1:9077/`.
- Graph rendering was observed in the panel.
- Wiring audit status was clean in the panel.
- No JavaScript errors were observed during panel checks.
- Desktop viewport had no horizontal overflow.
- Narrow viewport had no horizontal overflow.
- The graph had nodes and edges after loading.
- The panel remained usable after adding relay status display.
- These checks validate UI health, not browser relay correctness.
## 15 Live Runtime Started
- Root server was started from real `server.py`.
- Root server listened on `http://127.0.0.1:9077/`.
- Slot 1 was started as a managed slot.
- Slot 1 listened on `http://127.0.0.1:9078/`.
- Slot 2 was started as a managed slot.
- Slot 2 listened on `http://127.0.0.1:9079/`.
- Slot 2 auto-started the relay loop from `prompts/wiring_relay.json`.
- The live run used file-proxy cognition instead of LM Studio.
- The live run did not use manual browser automation by the coding agent.
## 16 Live Relay Request
- Slot 1 received a user-approved goal to run a browser AI review.
- Slot 1 planner cognition was serviced through `comms/slot1_cognition`.
- Slot 1 created a focused architecture and code packet for browser review.
- Slot 1 wrote browser relay request `slot1-1782422519826`.
- The browser relay request was written to `comms/llm_proxy/request.json`.
- The prompt length was about 30,923 characters.
- Slot 2 claimed the request.
- Slot 2 set `claimed_by_slot` to 2.
- Slot 2 began processing the relay request through its own graph.
## 17 Live Slot 2 Plan
- Slot 2 relay planner cognition was serviced through `comms/relay_cognition`.
- The relay plan had five steps.
- Step 1: focus the Google Chrome browser window.
- Step 2: navigate to `https://grok.com` if no usable chat composer is visible.
- Step 3: submit the exact request prompt into the visible chat composer.
- Step 4: wait until streaming or loading markers are absent.
- Step 5: remember the latest assistant answer into `MEMORY.llm_response`.
- The plan intentionally did not include direct response-file writing.
- Response writing is handled by the `llm_response_write` node after plan completion.
## 18 Live Slot 2 Observation
- Slot 2 advanced to the first plan step.
- Slot 2 ran the Endgame-AI observe node.
- The observed focused window was Task Manager.
- The observed desktop context included background Chrome.
- The observed Chrome window was titled `YouTube - Google Chrome`.
- The observation included desktop tree data.
- The observation included background Notepad and Codex windows.
- The observation showed Chrome but did not prove Grok was open.
- The next expected action was for Slot 2 to focus Chrome through Endgame action dispatch.
## 19 Live Proof Not Complete
- No Grok answer has been captured yet.
- No browser AI response has been written to `comms/llm_proxy/response.json` yet.
- Slot 1 has not yet consumed a browser answer through `MEMORY.llm_response`.
- Slot 2 has not yet submitted the review packet to a browser chat provider.
- Slot 2 has not yet demonstrated safe composer targeting.
- Slot 2 has not yet demonstrated wait-until-complete capture.
- Slot 2 has not yet demonstrated stale, echo, question, short, URL-only, or title-only rejection in this run.
- The relay queue split is implemented and partially exercised.
- The browser-relay backend remains an incomplete proof, not a deployment claim.
## 20 Codex As File-Proxy Cognition
- In the current proof, Codex/GPT acts as the external cognition backend.
- Endgame-AI writes LLM requests to file-proxy request files.
- The coding agent reads those request files.
- The coding agent writes matching response files with the same request IDs.
- Endgame-AI then consumes those responses as if they came from an LLM backend.
- This is intentional for bootstrapping and controlled validation.
- This is not LM Studio.
- This is not a mock server.
- It is the coding-agent file self-proxy backend in the intended architecture.
## 21 LM Studio Backend
- LM Studio can be used through the OpenAI-compatible transport.
- The config field is `transport: openai`.
- The default host field can point at `http://localhost:1234`.
- LM Studio must be running and serving a compatible model.
- Accounts are not needed for local LM Studio, but compute resources are.
- Local model quality can limit planning and action reliability.
- Local model latency can affect long ROD loops.
- Local model context limits can affect large browser relay packets.
- LM Studio availability was not required for the current file-proxy proof.
## 22 File Proxy Backend
- File proxy is the current default proof backend.
- File proxy allows an external coding agent to supply LLM responses.
- The request file contains model, messages, sampling settings, ID, and status.
- The response file must preserve the same request ID.
- The content must be parseable by the node that requested it.
- Reasoning can be stored separately in `reasoning_content`.
- Stale request and response files are archived.
- Separate per-slot queues avoid cross-consumption.
- File proxy is slow but inspectable and useful for bootstrap testing.
## 23 Browser Relay Backend
- Browser relay is the highest-risk backend.
- Slot 1 writes a browser handoff request to `comms/llm_proxy`.
- Slot 2 claims the handoff and controls the browser through Endgame-AI.
- Slot 2 submits the exact prompt to a visible browser chat composer.
- Slot 2 waits until streaming or loading has ended.
- Slot 2 captures only the latest assistant response.
- Slot 2 writes a matching browser handoff response.
- Slot 1 waits for and consumes that response.
- This backend is not proven until an end-to-end browser answer is captured and consumed.
## 24 Slot 1 Responsibilities
- Slot 1 is the main goal operator.
- Slot 1 plans user goals.
- Slot 1 decides when external intelligence is needed.
- Slot 1 writes relay handoff requests through the `llm_request` action.
- Slot 1 waits for relay answers through the `llm_wait_response` action.
- Slot 1 stores the returned answer in memory.
- Slot 1 should remain agnostic to the specific cognition backend.
- Slot 1 uses `prompts/wiring.json`.
- Slot 1 uses `prompts/model.json` unless overridden.
## 25 Slot 2 Responsibilities
- Slot 2 is the dedicated browser relay worker.
- Slot 2 polls `comms/llm_proxy/request.json`.
- Slot 2 claims pending relay requests.
- Slot 2 plans browser relay steps.
- Slot 2 observes the desktop before acting.
- Slot 2 acts only through declarative verbs and the action dispatcher.
- Slot 2 verifies outcomes and retries as wired.
- Slot 2 writes `comms/llm_proxy/response.json` after plan completion.
- Slot 2 uses `prompts/wiring_relay.json` and `prompts/model_relay.json`.
## 26 Root Server Responsibilities
- The root server owns the operator panel.
- The root server starts managed slots.
- The root server reports system status.
- The root server exposes `/slots/start`.
- The root server exposes `/slots/stop`.
- The root server exposes `/slots/run`.
- The root server exposes `/system`.
- The root server exposes `/relay/status`.
- The root server is not itself a proof of desktop/browser control.
## 27 ROD Graph Model
- ROD means reason about objective and decide the next step toward the goal.
- The graph is declarative wiring, not hard-coded chatbot flow.
- Nodes are configured in prompt wiring JSON.
- Edges define control flow between nodes.
- Rules constrain actions and verification behavior.
- Prompts define each circuit role.
- Reasoning storage captures circuit-level rationale.
- Hot reload allows wiring edits without rewriting core control flow.
- The project should preserve this graph-first design.
## 28 Wiring Audit
- Wiring audit checks graph shape and configuration consistency.
- Main wiring audit currently passes.
- Relay wiring audit currently passes.
- Audit success does not prove browser UI reliability.
- Audit success does not prove provider login state.
- Audit success does not prove response capture correctness.
- Audit failure should block deployment.
- Audit output should be collected with every proof run.
- Audit should be visible in the panel and via API.
## 29 Reasoning Chain Storage
- Reasoning chains are preserved in runtime state.
- Circuit reasoning can be stored under named keys.
- Relay planner reasoning is stored under the planner key.
- Relay action reasoning is stored under the act key.
- Relay verifier reasoning is stored under the verify key.
- Reasoning keys can be cleared on step confirmation.
- Reasoning storage helps debug why a step was chosen.
- Reasoning storage is evidence, not a substitute for action history.
- Reasoning storage should remain inspectable.
## 30 MoE Concepts
- MoE concepts remain part of the project.
- MoE routing should not be deleted.
- MoE routing should become inspectable and tied to real decisions.
- MoE should help route between specialized circuits or workers.
- MoE should not hide unsafe desktop action choices.
- MoE output should be traceable in the same state and trace files.
- MoE should be validated by wiring audit where possible.
- MoE should not block the queue split or relay proof.
- MoE is experimental until it demonstrates measurable routing value.
## 31 Self Feedback
- Reasoning self feedback remains part of the project.
- Self feedback should improve prompts, rules, or wiring based on observed failures.
- Self feedback must not erase safety constraints.
- Self feedback should be stored and reviewed.
- Self feedback should not silently claim success.
- Self feedback should be connected to verifier and reflector outcomes.
- Self feedback should produce bounded, reviewable changes.
- Self feedback is not a license for uncontrolled mutation.
- Self feedback should be part of future deployment hardening.
## 32 Self Modify
- Self modify remains available through validated wiring patches.
- Self modify should operate on wiring, prompts, rules, and limits.
- Self modify should not rewrite arbitrary repository files during normal operation.
- Self modify should respect schema validation.
- Self modify should respect operator approval.
- Self modify should keep old and new wiring inspectable.
- Self modify should not remove critical relay safety rules.
- Self modify should not remove hover scan or rendered desktop scope.
- Self modify should be treated as experimental until audited in live runs.
## 33 Desktop Observation
- Desktop observation is implemented in `desktop.py`.
- Observation captures focused window context.
- Observation captures rendered action targets.
- Observation captures desktop tree data.
- Observation includes hover scan when enabled.
- Observation should not assume UIA-only access is sufficient.
- Observation should distinguish focused, overlay, desktop, and background scopes.
- Observation output is used by action circuits, not by shell automation.
- Observation quality is critical for browser relay safety.
## 34 Hover Scan
- Hover scan is enabled by default.
- Hover scan probes the full screen.
- Hover scan can reveal controls not exposed by the focused UIA tree.
- Hover scan helps discover browser and overlay targets.
- Hover scan adds runtime cost.
- Hover scan should not be removed for relay proof.
- Hover scan output should be recorded in evidence.
- Hover scan failure can cause missing composer targets.
- Hover scan tuning belongs in wiring or observation config when possible.
## 35 Rendered Action Scope
- Rendered action scope defines what elements are safe action targets.
- `[ID]` targets are the primary click, write, and scroll targets.
- Background scope is informative but normally not direct target material.
- Focused and overlay scope are higher-confidence target areas.
- The relay action prompt must use screen IDs rather than hallucinated selectors.
- Address bar elements must be treated as forbidden for prompt submission.
- Chat composer elements must be positively identified.
- Rendered scope and UIA tree should be used together.
- Scope mistakes can cause destructive or privacy-sensitive actions.
## 36 Desktop Tree
- Desktop tree captures top-level windows and child controls.
- Desktop tree helps discover Chrome even when another app is focused.
- Desktop tree helped the live run identify `YouTube - Google Chrome`.
- Desktop tree also showed Codex, Notepad, Task Manager, and Program Manager.
- Desktop tree can be large and should be truncated carefully.
- Desktop tree is read-only context for most circuits.
- Desktop tree should not replace `[ID]` action targets.
- Desktop tree is critical evidence for real desktop observation.
- Desktop tree should stay enabled for relay testing.
## 37 Action Dispatch
- Actions are dispatched through `actions.py`.
- Supported declarative verbs include focus, click, write, press, hotkey, scroll, wait, and memory actions.
- The action dispatcher resolves targets from observation results.
- The action dispatcher uses desktop automation primitives.
- The action dispatcher handles long text by clipboard paste.
- The action dispatcher reports outcomes back to state.
- The graph verifies outcomes before advancing.
- Action dispatch is the only accepted path for browser actions in the proof.
- Manual browser automation by the coding agent does not count.
## 38 Long Text Paste
- Long text input uses a clipboard paste path.
- This matters because relay prompts can exceed 30,000 characters.
- Direct keystroke typing would be too slow and unreliable.
- Clipboard paste must still be targeted to the correct chat composer.
- Clipboard paste into the address bar is forbidden for relay prompts.
- Clipboard contents may contain repository excerpts approved by the operator.
- Clipboard actions should be recorded through action history.
- Long text paste should be tested against each browser provider.
- Provider-specific input limits remain an external constraint.
## 39 Action Safety
- The action layer must reject unsafe prompt submission targets.
- The action layer must not infer that any writable field is safe.
- The action layer must keep URL navigation separate from prompt submission.
- Navigation may use the address bar only for URL navigation steps.
- Prompt submission must use a browser chat composer.
- The relay plan should avoid unnecessary navigation away from a prepared chat tab.
- The relay verifier should confirm write and submit sequences.
- The relay reflector should retry or block on weak evidence.
- Safety rules should stay declarative where practical.
## 40 Address Bar Rule
- The relay must never type chat prompts into address bars.
- The relay must never type chat prompts into search bars.
- The relay must never type chat prompts into URL bars.
- The relay must never type chat prompts into location bars.
- The relay may use the address bar for URL navigation when the value is a URL.
- The relay must distinguish navigation text from chat prompt text.
- The relay wiring includes a rejection rule for address bar prompt writes.
- The live proof has not yet exercised this rejection end to end.
- Deployment requires recorded evidence that prompt writes target a chat composer.
## 41 Streaming Capture Rule
- The relay must not capture while the assistant is streaming.
- The relay must not capture while loading indicators are visible.
- The relay must not capture while thinking indicators are visible.
- The relay must not capture while stop buttons imply active generation.
- The relay should wait and observe again until completion evidence is present.
- Completion evidence is provider-specific and may change.
- The capture rule is represented in relay wiring.
- The live proof has not yet reached capture.
- Deployment requires evidence of waiting before capture.
## 42 Stale Capture Rejection
- The relay must not capture stale assistant answers.
- Stale answers are text that predates the current request.
- Stale answers can appear when opening an old chat tab.
- The relay must use current request context to reject stale text.
- The relay should prefer latest visible assistant answer.
- The relay should compare against prior memory and history where possible.
- Stale capture rejection is part of the relay safety contract.
- The live proof has not yet demonstrated stale rejection.
- Deployment requires a stale-chat negative test.
## 43 Prompt Echo Rejection
- The relay must not capture the submitted prompt as the assistant response.
- Browser chat pages often show the user prompt near the assistant answer.
- Long prompts increase the risk of echo capture.
- The relay must distinguish user message from assistant message.
- A captured response that mostly repeats the request must be rejected.
- A captured response equal to the current prompt must be rejected.
- A captured response dominated by repository packet text should be treated suspiciously.
- The live proof has not yet demonstrated prompt-echo rejection.
- Deployment requires evidence that the latest assistant answer was captured.
## 44 Question And Short Capture Rejection
- The relay must reject captures that are only questions back to the user.
- The relay must reject captures that are too short to be a useful answer.
- The relay must reject vague placeholder text.
- The relay must reject provider login prompts as answers.
- The relay must reject rate-limit notices as successful answers.
- A blocked provider state should be recorded as blocked, not success.
- Short-capture thresholds should be documented and tuned by provider.
- The live proof has not yet reached this capture path.
- Deployment requires negative tests for login, rate limit, and short answer states.
## 45 Title And URL Capture Rejection
- The relay must reject browser titles as assistant answers.
- The relay must reject URLs as assistant answers.
- The relay must reject address bar contents as assistant answers.
- The relay must reject tab labels as assistant answers.
- The relay must reject page navigation chrome as answer text.
- Title and URL captures are common in UIA-heavy browser reads.
- Rendered content and DOM-like text must be distinguished from browser chrome.
- The live proof has not yet captured an answer.
- Deployment requires evidence that captures come from chat content, not chrome.
## 46 Provider Fallback
- Preferred proof provider is Grok at `https://grok.com`.
- If Grok is blocked by login, account, or rate limits, try an authenticated visible provider.
- Allowed fallback providers include ChatGPT, Claude, Gemini, Perplexity, and Poe.
- Provider fallback must happen through Endgame-AI actions.
- Provider fallback should not bypass account terms or authentication.
- Provider fallback should record which provider was used.
- Provider fallback should record why the previous provider was blocked.
- No provider fallback has completed in the current run.
- Deployment should include at least one successful provider and one blocked-provider record.
## 47 Account And Rate Limits
- Browser AI access depends on existing authenticated sessions.
- Browser AI access depends on provider rate limits.
- Browser AI access depends on provider UI availability.
- Browser AI access depends on provider policy and safety filters.
- Browser AI access depends on local network state.
- Browser AI access depends on the browser profile and window state.
- Endgame-AI cannot guarantee provider availability.
- Documentation must state these limits.
- Deployment should include graceful blocked-state reporting.
## 48 Operator Approval
- The operator approved sharing the focused repository packet with Grok.
- The operator approved real desktop/browser testing through Endgame-AI.
- Approval does not remove provider limits.
- Approval does not remove local permission limits.
- Approval does not justify unsafe address-bar prompt writes.
- Approval does not justify claiming success before capture and consumption.
- Approval should be recorded in goal text or run evidence.
- Future sensitive file sharing should require explicit operator approval.
- Browser relay should support approval checkpoints for high-risk content.
## 49 Quick Start
- Open PowerShell in `C:\Users\px-wjt\Downloads\endgame-ai`.
- Confirm Python is available.
- Start root with `python server.py 9077`.
- Open the panel at `http://127.0.0.1:9077/`.
- Start managed slots from the panel or with `/slots/start`.
- Confirm Slot 1 health at `http://127.0.0.1:9078/health`.
- Confirm Slot 2 health at `http://127.0.0.1:9079/health`.
- Confirm `/system` reports the intended model paths and queues.
- Do not start a separate mock server for relay proof.
## 50 Starting Slots
- Root uses `server.py` to spawn slot processes.
- Slot ports are derived by slot number.
- Slot 1 normally uses port 9078.
- Slot 2 normally uses port 9079.
- Slot 2 uses `prompts/wiring_relay.json`.
- Slot 2 receives `ENDGAME_SLOT=2`.
- Slot 2 receives `ENDGAME_STATE=state.slot2.json`.
- Slot 2 receives `ENDGAME_MODEL=prompts/model_relay.json`.
- Slot health should be checked before submitting relay goals.
## 51 Servicing File Proxy
- Read the current request file for the correct slot queue.
- Preserve the exact `id` when writing a response.
- Write JSON to the matching response path.
- For Slot 1 cognition, use `comms/slot1_cognition`.
- For Slot 2 cognition, use `comms/relay_cognition`.
- Do not write Slot 2 cognition responses into `comms/llm_proxy`.
- Do not write browser relay responses by hand during a browser proof.
- Browser relay responses should be written by Slot 2 after capture.
- Manual file-proxy cognition is acceptable in this bootstrap run.
## 52 Browser Relay Proof Procedure
- Start root and managed slots from the real repository.
- Ensure Slot 2 is running the relay wiring.
- Submit a Slot 1 goal that requires browser relay intelligence.
- Service Slot 1 cognition through `comms/slot1_cognition`.
- Let Slot 1 write `comms/llm_proxy/request.json`.
- Let Slot 2 claim the relay request.
- Service Slot 2 cognition through `comms/relay_cognition`.
- Let Slot 2 focus, navigate, submit, wait, capture, and respond through Endgame-AI.
- Verify Slot 1 consumes `MEMORY.llm_response`.
## 53 Two-Message Review Target
- Message 1 should ask the browser AI to review the focused architecture and code packet.
- Message 1 should cover file proxy, slot management, desktop actions, wiring audit, relay nodes, model config, and relay wiring.
- Message 1 should request strengths, correctness risks, concrete fixes, and proof required.
- Message 2 should ask whether the observed behavior proves correctness.
- Message 2 should ask what must be fixed before claiming the relay works.
- Both messages should be submitted through Endgame-AI browser actions.
- Both responses should be captured through Endgame-AI observation.
- Both responses should be returned through `comms/llm_proxy`.
- The current live run has not completed Message 1 submission.
## 54 Evidence To Collect
- `/system` output from root.
- `/relay/status` output from root.
- `/wiring/audit` output for main wiring.
- `/wiring/audit` output for relay wiring.
- `/state` output from Slot 1.
- `/state` output from Slot 2.
- `state.slot1.json` after Slot 1 consumes the relay answer.
- `state.slot2.json` after Slot 2 writes the relay answer.
- Relevant proxy archive files and action history excerpts.
## 55 Deployment Definition
- Deployment means the system can run real goals locally with clear limits.
- Deployment means static validation is clean.
- Deployment means the panel loads and exposes status.
- Deployment means Slot 1 and Slot 2 use separate cognition queues.
- Deployment means browser relay has at least one successful end-to-end provider proof.
- Deployment means blocked provider states are recorded honestly.
- Deployment means safety rules are enforced and evidenced.
- Deployment means recovery procedures are documented.
- Deployment does not mean unlimited autonomy or guaranteed provider access.
## 56 Predeployment Checklist
- Run JSON parse checks for all prompt and model files.
- Run `python -m compileall -q .`.
- Run `python -m pyright server.py colony.py desktop.py`.
- Run `git diff --check`.
- Run `server.wiring_audit()` for main wiring.
- Run `server.wiring_audit()` for relay wiring.
- Load root panel at `http://127.0.0.1:9077/`.
- Check graph render, audit status, JS errors, and overflow.
- Complete the browser relay runtime proof.
## 57 Deployment Blockers
- Browser relay has not yet submitted the review prompt to Grok in the current run.
- Browser relay has not yet captured a completed assistant answer.
- Browser relay has not yet written `comms/llm_proxy/response.json` from Slot 2.
- Slot 1 has not yet consumed browser relay output through memory.
- Composer targeting has not yet been evidenced.
- Streaming-complete wait has not yet been evidenced.
- Negative capture rejection has not yet been evidenced.
- Provider fallback has not yet been tested.
- These blockers should prevent a production-ready claim.
## 58 Reliability Gaps
- Browser UI changes can break composer detection.
- Provider login states can block submission.
- Provider rate limits can block response generation.
- UIA can expose browser chrome more reliably than page content.
- Large prompt paste can fail or truncate.
- Window focus can be stolen by other applications.
- Hover scan can miss controls depending on timing and scale.
- Response capture can confuse old messages with new answers.
- Long-running loops need better progress telemetry.
## 59 Observability Gaps
- The panel should show per-slot active request IDs.
- The panel should show current slot resume node.
- The panel should show last action and last verifier outcome.
- The panel should show relay request claimed status clearly.
- The panel should show browser provider candidate state.
- The panel should show whether capture was blocked by streaming indicators.
- The panel should link to relevant archived request and response files.
- The panel should separate source validation from runtime proof.
- The panel should avoid hiding long error strings.
## 60 Recovery
- If a cognition request is stale, clear the correct cognition proxy queue.
- If a browser relay request is stale, clear `/relay/clear` with confirmation.
- If Slot 2 is stuck, inspect `state.slot2.json`.
- If Slot 2 has no request, inspect `comms/llm_proxy/request.json`.
- If Slot 2 has a cognition request, service `comms/relay_cognition`.
- If Slot 1 is waiting, inspect `MEMORY.llm_request_id`.
- If the browser provider is blocked, record blocked status and try fallback.
- If address-bar prompt submission is attempted, stop and fix wiring or action selection.
- If capture is weak, retry observe and wait rather than writing success.
## 61 Troubleshooting No Request
- Check whether the expected request file exists.
- Check whether the request file was archived.
- Check whether the response file already exists.
- Check whether the request ID changed.
- Check `/health` for the active model path.
- Check `/system` for active proxy paths.
- Check that Slot 1 and Slot 2 are not using the same cognition queue.
- Check that `ENDGAME_MODEL` is set for Slot 2.
- Check whether a previous run left a stale response.
## 62 Troubleshooting Slot 2 At Observe
- Inspect `state.slot2.json`.
- Check `_resume_node`.
- If `_resume_node` is `observe`, the next graph step should observe the desktop.
- If `_resume_node` is `act`, a relay cognition request should usually exist.
- Check `comms/relay_cognition/request.json`.
- Check whether the file-proxy response ID matches the request ID.
- Check whether the run thread is active via `/health`.
- Check whether desktop observation is slow due to hover scan.
- Do not bypass by manually focusing the browser.
## 63 Troubleshooting Browser Focus
- Confirm Chrome is listed in desktop tree or taskbar.
- Use Endgame-AI action `focus` with target `Chrome` when appropriate.
- Verify focus by observing `FOCUSED: ... Google Chrome`.
- Do not use external browser automation for the proof.
- If focus fails, inspect window titles.
- If focus opens the wrong browser window, observe and retry.
- If Chrome is minimized, the focus action should restore or activate it if supported.
- If no browser exists, the run should block or launch according to wiring policy.
- Focus success alone is not browser relay success.
## 64 Troubleshooting Navigation
- Navigate to `https://grok.com` only if no usable chat composer is visible.
- URL navigation may use address bar actions.
- Prompt submission may not use address bar actions.
- Verify page load by observing Grok or a fallback provider.
- If Grok is unauthenticated, record the blocked state.
- If Grok is rate-limited, record the blocked state.
- If a different authenticated chat provider is visible, fallback may be acceptable.
- Provider choice should be recorded in state or telemetry.
- Navigation success alone is not browser relay success.
## 65 Troubleshooting Composer Targeting
- A valid composer is a writable chat input area.
- Address, search, URL, and location bars are invalid for prompt submission.
- Browser page search fields are invalid unless they are clearly the chat composer.
- The target line should contain labels such as ask, message, prompt, or chat.
- The target line should not contain URL, address, search, location, or omnibox labels.
- If no composer is visible, wait, scroll, or navigate through Endgame-AI actions.
- Do not paste the prompt into an unverified field.
- The action history must show write then submit into the composer.
- Composer targeting evidence is required for deployment.
## 66 Troubleshooting Capture
- Observe after submission before capture.
- Wait while streaming, loading, thinking, or stop-generation indicators are present.
- Capture the latest assistant message, not the user prompt.
- Reject captures that are too short.
- Reject captures that are mostly the prompt.
- Reject captures that are only questions or provider chrome.
- Reject captures that are URLs or tab titles.
- Store the accepted answer in `MEMORY.llm_response`.
- Write the relay response only after accepted capture.
## 67 Validation Commands
- JSON parse all prompt and model files.
- Compile Python with `python -m compileall -q .`.
- Type check focused files with `python -m pyright server.py colony.py desktop.py`.
- Check whitespace with `git diff --check`.
- Query root health with `Invoke-WebRequest http://127.0.0.1:9077/health`.
- Query root system with `Invoke-WebRequest http://127.0.0.1:9077/system`.
- Query relay status with `Invoke-WebRequest http://127.0.0.1:9077/relay/status`.
- Query Slot 1 health with `Invoke-WebRequest http://127.0.0.1:9078/health`.
- Query Slot 2 health with `Invoke-WebRequest http://127.0.0.1:9079/health`.
## 68 Commit Policy
- Commit only after validation and runtime evidence are complete or honestly documented.
- Do not commit stale runtime files unless explicitly promoted.
- Do not commit credentials, browser sessions, or provider tokens.
- Do not commit manual temporary scripts.
- Keep source edits scoped to the relay split, docs, panel, and necessary fixes.
- Preserve MoE, self feedback, self modify, hover scan, and desktop tree concepts.
- Do not revert unrelated user changes.
- Use clear commit messages tied to relay completion work.
- If browser proof remains blocked, say blocked in the commit or handover.
## 69 What Was Done
- Split Slot 1 cognition from Slot 2 cognition.
- Kept browser relay handoff separate from both cognition queues.
- Added per-slot model config support through `ENDGAME_MODEL`.
- Added `prompts/model_relay.json`.
- Updated `prompts/model.json`.
- Added relay status and relay clear APIs.
- Updated the panel to show cognition and browser relay status separately.
- Updated setup and rationale docs.
- Ran static, audit, and panel validation successfully.
## 70 What Is Left
- Finish Slot 2 browser focus through Endgame-AI action dispatch.
- Navigate to Grok or an authenticated fallback through Endgame-AI actions if needed.
- Submit the exact review packet into a verified chat composer.
- Wait until the browser AI response is complete.
- Capture only the latest assistant answer.
- Write `comms/llm_proxy/response.json` from Slot 2.
- Let Slot 1 consume the answer through `MEMORY.llm_response`.
- Run the follow-up review message.
- Collect evidence and then commit the completed implementation.
