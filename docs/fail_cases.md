# Playtest Fail Cases

Specific failures observed during the 10-turn Dead Drop playtest, documented as regression test cases.

## 1. Zero Rolls in Chase Sequence

**Description**: Player used `move` to flee during an active pursuit. Engine classified `move` as safe (no roll needed), so the player auto-succeeded escape with no tension.

**Expected behavior**: Moving while being pursued should require a roll. The interpreter should flag `risk_flags: ["pursuit", "dangerous"]`, and the resolver should recognize that risk flags override the safe classification.

**Root cause**: `_needs_roll()` had no mechanism to override safe actions based on context. Interpreter `risk_flags` were generated but never consumed by the resolver.

**Fix**: Resolver `_needs_roll()` now accepts `risk_flags` parameter. If a safe action has risk flags matching `{"violence", "contested", "dangerous", "pursuit", "hostile_present"}`, it requires a roll. Interpreter prompt updated with contextual risk flag guidance.

## 2. Time Clock Drained Too Fast (8 to 0 in ~15 Minutes)

**Description**: Time clock went from 8 to 0 within approximately 15 fictional minutes. Every action, including instant physical actions like moving across a room or examining something, cost `time: 1`.

**Expected behavior**: Physical actions (move, sneak, climb, use, look, examine) should cost zero time. Only information-gathering (search, investigate, talk, hack) and travel should cost time. Unknown actions should default to zero cost.

**Root cause**: `_default` cost was `{"time": 1}`, and `move`, `examine`, `go` all explicitly cost `{"time": 1}`.

**Fix**: Updated `cyberpunk_noir_clock_rules()` cost_map. `_default` is now `{}`. Physical actions explicitly mapped to `{}`. Travel costs `{"time": 2}` to reflect significant movement.

## 3. NPC Did 5-6 Actions in One Turn

**Description**: In a single turn where the player performed one action (attempt to flee), the narrator had NPCs surround the building, deploy surveillance drones, AND close from above simultaneously.

**Expected behavior**: NPCs should get roughly one action-equivalent per turn, matching the player's single action. NPCs can react to the player's action and continue one ongoing activity, but not execute a multi-step tactical plan.

**Root cause**: No guidance in narrator prompt about temporal parity between player and NPC actions.

**Fix**: Added "Temporal Parity (CRITICAL)" section to narrator prompt with explicit rules and a self-test: "Count the NPC actions in your draft. If NPCs did more than 2 distinct things, cut back."

## 4. Sneak Succeeded but Agent Spotted Player

**Description**: Engine resolved a sneak action as `action_succeeded`, but the narrator described the corporate agent immediately spotting the player anyway.

**Expected behavior**: When the engine says an action succeeded, the narrative must reflect that success. A successful sneak means the player is undetected.

**Root cause**: Engine events only said `action_succeeded` with minimal details. The narrator didn't have clear guidance on what "sneak succeeded" means in concrete terms.

**Fix**: Added `outcome_state` field to success events (e.g., "Player is undetected and in a concealed position" for sneak). Added `failure_state` for failures. Narrator prompt already has "Success Must Matter" section; outcome_state gives it concrete data to work with.

## 5. Agent Knew About Player-Discovered Hatch

**Description**: Player discovered a maintenance hatch during exploration. On the very next turn, the pursuing corporate agent said "check the maintenance hatch" despite having no way to know about it.

**Expected behavior**: NPCs should only act on information they could plausibly have. An NPC with no line of sight to the hatch discovery should not reference it.

**Root cause**: No guidance in narrator prompt about NPC information limits.

**Fix**: Added "NPC Information Limits" section to narrator prompt. NPCs must act on their last known information, not omniscient knowledge. Before writing NPC actions, narrator must ask "How would this NPC know that?"

## 6. Re-Searched Jin's Body on Turn 2

**Description**: Player searched Jin's body on turn 1 (found items). On turn 2, player said something like "check Jin again" and the interpreter proposed another `search` action, which succeeded and produced duplicate discoveries.

**Expected behavior**: The interpreter should check facts for `investigated_by_player` entries before proposing a search. If already searched, propose `examine` instead and note the deduplication.

**Root cause**: No search deduplication logic in interpreter prompt.

**Fix**: Added "Search Deduplication" section to interpreter prompt. Also added search dedup guidance to narrator prompt for narrative acknowledgment.

## 7. Item Not Auto-Picked-Up on Search

**Description**: Player searched Jin's body and the narrator described finding a data chip, but on the next turn the chip wasn't in inventory. Player had to explicitly say "grab the chip" to add it.

**Expected behavior**: When a search succeeds, found items should be implicitly picked up. Finding it means taking it (unless too large or fixed in place).

**Root cause**: No guidance about implicit item pickup in narrator prompt. The `introduced_items` mechanism existed but the narrator didn't always use it, and there was no rule about search implying pickup.

**Fix**: Added "Search and Discovery Rules" section to narrator prompt stating that search success implies pickup. Items in `discoveries` with `item_found` type are now in the player's possession.

## 8. Clock Hit 0, Nothing Happened

**Description**: Time clock reached 0 (triggers: "Deadline passed, consequences arrive") but no narrative consequence was described. The game continued as if nothing happened.

**Expected behavior**: When a clock crosses a trigger threshold, the narrative should reflect the consequence. Clock triggers should be dramatic moments.

**Root cause**: Clock triggers were being computed and injected as `clock_triggered` engine events, but the narrator may not have given them enough weight. Additionally, resolver output (including trigger info) was not persisted to the events table for post-game analysis.

**Fix**: Added resolver output to `pass_outputs` in event persistence. Clock trigger events were already being injected before narrator stage; the narrator prompt sections on clock handling should now work more effectively with the richer engine event data.

## 9. Three Failures While Hunted, No Capture

**Description**: Player failed 3 consecutive sneak attempts while a high-threat corporate agent was actively hunting them. Each failure added heat+1, but the player was never caught, cornered, or harmed. The agent stayed perpetually "closing in" without arriving.

**Expected behavior**: Consecutive failures during an active threat should escalate. At threshold (3), the threat should resolve against the player mechanically — capture, harm, cornering. The engine should not leave the player in a failed-but-consequence-free loop.

**Root cause**: No failure severity system. All failures applied the same flat consequence regardless of context danger level. No streak tracking or escalation mechanism.

**Fix**: Added context-sensitive failure severity (3 tiers: safe/risky/dangerous), situation facts that persist mechanical states (exposed/detected/cornered), and a failure streak system that resolves threats against the player at threshold. Physical failures during active threat now cause harm. Binding engine events force the narrator to respect the resolution outcome.

## 10. Narrator Contradicts Engine on Failed Sneak

**Description**: Engine resolved a sneak as `action_failed` and set `failure_state: "Player was detected"`, but the narrator wrote the player as hidden and undetected. The narrative didn't match the mechanical reality.

**Expected behavior**: When the engine says a sneak failed and the player is detected, the narrative must reflect detection. The narrator cannot override engine outcomes.

**Root cause**: No persistent mechanical state to force the narrator. `failure_state` was a hint but non-binding. The narrator could (and did) ignore it in favor of more dramatic prose.

**Fix**: Failed actions at tier 1+ now create persistent situation facts (e.g., `exposed` condition) that appear in the context packet's `active_situations` section. The narrator prompt now has a CRITICAL section requiring it to respect these as non-negotiable engine states. The situation persists until the engine clears it via a specific success action.

## 11. NPC Capability Inflation — Agent Detects Neural Chip Access

**Description**: The narrator described a corporate agent remotely detecting the player's neural chip access. The agent had no netrunning capabilities — this was a narratively convenient but mechanically unsupported ability.

**Expected behavior**: NPCs can only use abilities from their defined capabilities and equipment. An agent with `no_netrunning` limitation cannot perform any cyber-related detection or hacking.

**Root cause**: No NPC capability system. The narrator was free to invent whatever abilities seemed dramatically appropriate.

**Fix**: Added NPC capability system — `threat_level`, `capabilities`, `equipment`, `limitations`, and `escalation_profile` fields on NPC entities. These appear in the context packet as `npc_capabilities`. The narrator prompt now has a CRITICAL section requiring NPCs to only use defined capabilities and respect their limitations. When no capabilities are defined, conservative defaults apply based on role.
