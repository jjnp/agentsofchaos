const assert = require('assert');
const { execFileSync } = require('child_process');
const WebSocket = require('ws');

const url = process.env.ORCHESTRATOR_URL || 'ws://127.0.0.1:3000';
const ws = new WebSocket(url);
const listeners = [];
const slotState = new Map();

function ensureSlot(slot) {
  if (!slotState.has(slot)) {
    slotState.set(slot, {
      label: `pi-${slot + 1}`,
      agentUuid: null,
      containerName: null,
      lastGitStatus: null,
    });
  }
  return slotState.get(slot);
}

function waitFor(predicate, timeoutMs = 240000, label = 'event') {
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

function dispatch(event) {
  if (typeof event.slot === 'number') {
    const slot = ensureSlot(event.slot);
    if (event.label) slot.label = event.label;
    if (event.agentUuid) slot.agentUuid = event.agentUuid;
    if (event.containerName) slot.containerName = event.containerName;
    if (event.type === 'git_status') slot.lastGitStatus = event.status;
  }

  for (let i = 0; i < listeners.length; i += 1) {
    if (listeners[i](event)) {
      listeners.splice(i, 1);
      return;
    }
  }
}

function send(payload) {
  ws.send(JSON.stringify(payload));
}

function dockerExec(containerName, command) {
  return execFileSync('sudo', ['docker', 'exec', containerName, 'sh', '-lc', command], { encoding: 'utf8' }).trim();
}

async function waitForReady() {
  await waitFor((event) => event.type === 'grid_ready', 120000, 'grid_ready');
}

async function createInstance() {
  send({ type: 'create_instance' });
  return await waitFor((event) => event.type === 'instance_created', 120000, 'instance_created');
}

async function runPrompt(slot, message) {
  send({ type: 'prompt', target: slot, message });
  await waitFor((event) => event.slot === slot && event.type === 'pi_event' && event.event?.type === 'agent_end', 600000, `agent_end slot ${slot}`);
}

async function runFork(sourceSlot) {
  send({ type: 'fork', source: sourceSlot });
  return await waitFor((event) => event.type === 'fork_complete' && event.sourceSlot === sourceSlot, 240000, `fork_complete from ${sourceSlot}`);
}

async function runMerge(sourceSlot, targetSlot) {
  send({ type: 'merge', source: sourceSlot, target: targetSlot });
  return await waitFor((event) => event.type === 'merge_complete' && event.sourceSlot === sourceSlot && event.targetSlot === targetSlot, 600000, `merge_complete ${sourceSlot}->${targetSlot}`);
}

ws.on('message', (buffer) => {
  const event = JSON.parse(buffer.toString('utf8'));
  console.log(JSON.stringify(event));
  dispatch(event);
});

ws.on('open', async () => {
  try {
    await waitForReady();

    const root = await createInstance();
    const rootSlot = root.slot;

    await runPrompt(rootSlot, [
      'Using bash only, run exactly this shell command:',
      'cd /workspace && printf "%s" "base-start" > merge_demo_base.txt && git add -A && git commit -m "base merge demo"',
      'Do not just explain; execute the command.'
    ].join(' '));

    const fork = await runFork(rootSlot);
    const childSlot = fork.targetSlot;

    await runPrompt(rootSlot, [
      'Using bash only, run exactly this shell command:',
      'cd /workspace && printf "%s" "target-change" > merge_demo_target.txt && git add -A && git commit -m "target change"',
      'Do not just explain; execute the command.'
    ].join(' '));

    await runPrompt(childSlot, [
      'Using bash only, run exactly this shell command:',
      'cd /workspace && printf "%s" "source-change" > merge_demo_source.txt && git add -A && git commit -m "source change"',
      'Do not just explain; execute the command.'
    ].join(' '));

    const merge = await runMerge(childSlot, rootSlot);
    assert.strictEqual(merge.mergeExitCode, 0, 'expected clean merge into integration instance');

    const integrationSlot = merge.integrationSlot;
    assert.ok(Number.isInteger(integrationSlot), 'merge should create an integration slot');

    const rootState = ensureSlot(rootSlot);
    const childState = ensureSlot(childSlot);
    const integrationState = ensureSlot(integrationSlot);

    assert.ok(rootState.containerName, 'root containerName missing');
    assert.ok(childState.containerName, 'child containerName missing');
    assert.ok(integrationState.containerName, 'integration containerName missing');

    const rootFiles = dockerExec(rootState.containerName, 'ls -1 /workspace | sort');
    const childFiles = dockerExec(childState.containerName, 'ls -1 /workspace | sort');
    const integrationFiles = dockerExec(integrationState.containerName, 'ls -1 /workspace | sort');

    assert.match(rootFiles, /merge_demo_base\.txt/);
    assert.match(rootFiles, /merge_demo_target\.txt/);
    assert.doesNotMatch(rootFiles, /merge_demo_source\.txt/);

    assert.match(childFiles, /merge_demo_base\.txt/);
    assert.match(childFiles, /merge_demo_source\.txt/);
    assert.doesNotMatch(childFiles, /merge_demo_target\.txt/);

    assert.match(integrationFiles, /merge_demo_base\.txt/);
    assert.match(integrationFiles, /merge_demo_target\.txt/);
    assert.match(integrationFiles, /merge_demo_source\.txt/);

    const integrationStatus = dockerExec(integrationState.containerName, 'git -C /workspace status --short --branch');
    assert.match(integrationStatus, /^## main/);
    assert.ok(!/^(AA|UU|DU|UD|DD|AU|UA) /m.test(integrationStatus), 'integration instance should not be conflicted');

    const mergeContext = dockerExec(integrationState.containerName, 'test -f /state/meta/merge-context.md && cat /state/meta/merge-context.md');
    assert.match(mergeContext, /# Merge Context/);

    console.log('E2E smoke flow completed.');
    console.log(JSON.stringify({
      rootSlot,
      childSlot,
      integrationSlot,
      rootContainer: rootState.containerName,
      childContainer: childState.containerName,
      integrationContainer: integrationState.containerName,
    }));
    ws.close();
  } catch (error) {
    console.error(error);
    process.exitCode = 1;
    ws.close();
  }
});
