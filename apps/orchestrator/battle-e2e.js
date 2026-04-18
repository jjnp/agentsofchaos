const WebSocket = require('ws');

const url = process.env.ORCHESTRATOR_URL || 'ws://127.0.0.1:3000';
const ws = new WebSocket(url);
const listeners = [];
const events = [];
const slots = new Map();

function log(...args) {
  console.log(new Date().toISOString(), ...args);
}

function ensureSlot(slot) {
  if (!slots.has(slot)) slots.set(slot, {});
  return slots.get(slot);
}

function dispatch(event) {
  events.push(event);
  if (typeof event.slot === 'number') {
    const slot = ensureSlot(event.slot);
    if (event.label) slot.label = event.label;
    if (event.agentUuid) slot.agentUuid = event.agentUuid;
    if (event.containerName) slot.containerName = event.containerName;
    if (event.type === 'git_status') slot.gitStatus = event.status;
  }
  for (let i = 0; i < listeners.length; i += 1) {
    if (listeners[i](event)) {
      listeners.splice(i, 1);
      return;
    }
  }
}

function waitFor(predicate, timeoutMs = 300000, label = 'event') {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`Timed out waiting for ${label}`)), timeoutMs);
    listeners.push((event) => {
      if (!predicate(event)) return false;
      clearTimeout(timer);
      resolve(event);
      return true;
    });
  });
}

function send(payload) {
  ws.send(JSON.stringify(payload));
}

async function createInstance() {
  send({ type: 'create_instance' });
  const event = await waitFor((e) => e.type === 'instance_created', 120000, 'instance_created');
  log('instance_created', event.slot, event.label, event.agentUuid);
  return event;
}

async function prompt(slot, message, label) {
  log('prompt_start', slot, label);
  send({ type: 'prompt', target: slot, message });
  const event = await waitFor((e) => e.slot === slot && e.type === 'pi_event' && e.event?.type === 'agent_end', 600000, `agent_end ${slot}`);
  log('prompt_end', slot, label);
  return event;
}

async function fork(sourceSlot) {
  log('fork_start', sourceSlot);
  send({ type: 'fork', source: sourceSlot });
  const event = await waitFor((e) => e.type === 'fork_complete' && e.sourceSlot === sourceSlot, 300000, `fork_complete ${sourceSlot}`);
  log('fork_end', sourceSlot, '->', event.targetSlot);
  return event;
}

async function prepareMerge(sourceSlot, targetSlot) {
  log('prepare_merge_start', sourceSlot, '->', targetSlot);
  send({ type: 'prepare_merge', source: sourceSlot, target: targetSlot });
  const event = await waitFor((e) => e.type === 'merge_prep_complete' && e.sourceSlot === sourceSlot && e.targetSlot === targetSlot, 300000, `merge_prep_complete ${sourceSlot}->${targetSlot}`);
  log('prepare_merge_end', sourceSlot, '->', targetSlot, event.remoteName, event.bytes);
  return event;
}

async function merge(sourceSlot, targetSlot) {
  log('merge_start', sourceSlot, '->', targetSlot);
  send({ type: 'merge', source: sourceSlot, target: targetSlot });
  const event = await waitFor((e) => e.type === 'merge_complete' && e.sourceSlot === sourceSlot && e.targetSlot === targetSlot, 600000, `merge_complete ${sourceSlot}->${targetSlot}`);
  log('merge_end', sourceSlot, '->', targetSlot, 'integration', event.integrationSlot, 'exit', event.mergeExitCode);
  return event;
}

async function stop(slot) {
  log('stop_start', slot);
  send({ type: 'stop_instance', target: slot });
  const event = await waitFor((e) => e.type === 'instance_stopped' && e.slot === slot, 180000, `instance_stopped ${slot}`);
  log('stop_end', slot);
  return event;
}

ws.on('message', (buffer) => {
  const event = JSON.parse(buffer.toString('utf8'));
  dispatch(event);
});

ws.on('open', async () => {
  try {
    await waitFor((e) => e.type === 'grid_ready', 120000, 'grid_ready');
    log('grid_ready');

    const root = await createInstance();
    const rootSlot = root.slot;

    await prompt(
      rootSlot,
      'Using bash only, run exactly this shell command: cd /workspace && printf "base\n" > battle_base.txt && printf "base\n" > battle_conflict.txt && git add -A && git commit -m "battle base" Do not just explain; execute the command.',
      'base commit',
    );

    const forkA = await fork(rootSlot);
    const forkB = await fork(rootSlot);
    const slotA = forkA.targetSlot;
    const slotB = forkB.targetSlot;

    await prompt(
      rootSlot,
      'Using bash only, run exactly this shell command: cd /workspace && printf "root-side\n" > battle_root_only.txt && printf "root-change\n" > battle_conflict.txt && git add -A && git commit -m "root branch changes" Do not just explain; execute the command.',
      'root divergence',
    );

    await prompt(
      slotA,
      'Using bash only, run exactly this shell command: cd /workspace && printf "branch-a\n" > battle_branch_a_only.txt && git add -A && git commit -m "branch a clean change" Do not just explain; execute the command.',
      'branch A clean change',
    );

    await prompt(
      slotB,
      'Using bash only, run exactly this shell command: cd /workspace && printf "branch-b-change\n" > battle_conflict.txt && printf "branch-b\n" > battle_branch_b_only.txt && git add -A && git commit -m "branch b conflict change" Do not just explain; execute the command.',
      'branch B conflict change',
    );

    const prep = await prepareMerge(slotA, rootSlot);
    const cleanMerge = await merge(slotA, rootSlot);
    const conflictMerge = await merge(slotB, rootSlot);

    const summary = {
      rootSlot,
      slotA,
      slotB,
      mergePrepRemote: prep.remoteName,
      cleanIntegrationSlot: cleanMerge.integrationSlot,
      cleanMergeExitCode: cleanMerge.mergeExitCode,
      conflictIntegrationSlot: conflictMerge.integrationSlot,
      conflictMergeExitCode: conflictMerge.mergeExitCode,
      stopped: [],
    };

    for (const slot of [slotA, slotB, cleanMerge.integrationSlot, conflictMerge.integrationSlot, rootSlot]) {
      await stop(slot);
      summary.stopped.push(slot);
    }

    const bridgeErrors = events.filter((e) => e.type === 'bridge_error');
    const mergeSucceededEvents = events.filter((e) => e.type === 'git_merge_succeeded');
    const mergeConflictedEvents = events.filter((e) => e.type === 'git_merge_conflicted');
    const mergeContextEvents = events.filter((e) => e.type === 'merge_context_written');
    summary.bridgeErrors = bridgeErrors.length;
    summary.mergeSucceededEvents = mergeSucceededEvents.length;
    summary.mergeConflictedEvents = mergeConflictedEvents.length;
    summary.mergeContextEvents = mergeContextEvents.length;

    console.log('FINAL_SUMMARY ' + JSON.stringify(summary, null, 2));
    ws.close();
  } catch (error) {
    console.error('BATTLE_TEST_ERROR', error);
    process.exitCode = 1;
    ws.close();
  }
});
