const WebSocket = require('ws');

const url = process.env.ORCHESTRATOR_URL || 'ws://127.0.0.1:3000';
const ws = new WebSocket(url);

function waitFor(predicate, timeoutMs = 180000) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('Timed out waiting for event')), timeoutMs);
    listeners.push((event) => {
      if (!predicate(event)) return false;
      clearTimeout(timer);
      resolve(event);
      return true;
    });
  });
}

const listeners = [];
function dispatch(event) {
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

async function waitForReady() {
  await waitFor((event) => event.type === 'grid_ready', 120000);
}

async function runPrompt(slot, message) {
  send({ type: 'prompt', target: slot, message });
  await waitFor((event) => event.slot === slot && event.type === 'pi_event' && event.event?.type === 'agent_end');
}

async function runFork(source, target) {
  send({ type: 'fork', source, target });
  await waitFor((event) => event.type === 'fork_complete' && event.sourceSlot === source && event.targetSlot === target);
}

async function runMerge(source, target) {
  send({ type: 'merge', source, target });
  await waitFor((event) => event.type === 'merge_complete' && event.sourceSlot === source && event.targetSlot === target, 240000);
}

ws.on('message', (buffer) => {
  const event = JSON.parse(buffer.toString('utf8'));
  console.log(JSON.stringify(event));
  dispatch(event);
});

ws.on('open', async () => {
  try {
    await waitForReady();

    await runPrompt(0, 'Using bash, create a file named root.txt in /workspace with the text root-start and then git add and git commit it with a short message.');
    await runFork(0, 1);
    await runFork(0, 2);

    await runPrompt(1, 'Using bash, append a new line alpha-branch to /workspace/root.txt and commit the change.');
    await runPrompt(2, 'Using bash, append a new line beta-branch to /workspace/root.txt and commit the change.');

    await runMerge(1, 0);
    await runMerge(2, 0);

    console.log('E2E smoke flow completed.');
    ws.close();
  } catch (error) {
    console.error(error);
    process.exitCode = 1;
    ws.close();
  }
});
