import { qs } from './dom.js';
import { CardManager } from './cards.js';
import { LineageStore } from './lineage.js';
import { createSocket } from './socket.js';

const statusEl = qs('status');
const metaEl = qs('meta');
const gridEl = qs('grid');
const templateEl = qs('cardTemplate');
const newInstanceBtn = qs('newInstance');

let ws;
const cardManager = new CardManager(gridEl, templateEl, (payload) => {
  if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify(payload));
});
const lineage = new LineageStore();

function setStatus(text) {
  statusEl.textContent = text;
}

function refreshLineage(slot) {
  if (!cardManager.has(slot)) return;
  cardManager.setLineage(slot, lineage.format(slot));
}

function handleLifecycleEvent(payload) {
  if (payload.type === 'grid_boot') {
    metaEl.textContent = `${payload.model} • merge ${payload.mergeModel} • session ${payload.session}`;
    return true;
  }
  if (payload.type === 'grid_ready') {
    setStatus('Ready');
    return true;
  }
  if (payload.type === 'instance_created') {
    cardManager.create(payload.slot);
    lineage.ensure(payload.slot);
    if (payload.agentUuid) lineage.setAgent(payload.slot, payload.agentUuid);
    refreshLineage(payload.slot);
    return true;
  }
  if (payload.type === 'instance_stopped') {
    cardManager.remove(payload.slot);
    lineage.remove(payload.slot);
    setStatus(`Stopped instance ${payload.slot + 1}`);
    return true;
  }
  return false;
}

function handleInstanceEvent(payload) {
  if (typeof payload.slot === 'number') {
    if (!cardManager.has(payload.slot)) cardManager.create(payload.slot);
    lineage.ensure(payload.slot);
    cardManager.pushEvent(payload.slot, payload);
  }

  if (payload.type === 'session_ready') {
    if (payload.agentUuid) lineage.setAgent(payload.slot, payload.agentUuid);
    cardManager.setMeta(payload.slot, `${payload.label} • ${payload.agentUuid}`);
    refreshLineage(payload.slot);
    return true;
  }
  if (payload.type === 'session_output') {
    cardManager.appendTerminal(payload.slot, payload.text);
    return true;
  }
  if (payload.type === 'session_exit') {
    cardManager.setMeta(payload.slot, `${payload.label} exited`);
    return true;
  }
  return false;
}

function handleActionEvent(payload) {
  const statuses = {
    fork_start: `Forking instance ${payload.sourceSlot + 1}...`,
    fork_complete: `Fork complete: ${payload.sourceSlot + 1} -> ${payload.targetSlot + 1}`,
    merge_prep_start: `Preparing bundle from ${payload.sourceSlot + 1} into ${payload.targetSlot + 1}...`,
    merge_prep_complete: `Bundle prepared: ${payload.sourceSlot + 1} -> ${payload.targetSlot + 1}`,
    merge_start: `Merging ${payload.sourceSlot + 1} into ${payload.targetSlot + 1}...`,
    merge_complete: `Merge finished: ${payload.sourceSlot + 1} -> ${payload.targetSlot + 1}`,
  };

  if (payload.type === 'fork_complete') {
    lineage.markFork(payload.sourceSlot, payload.targetSlot);
    refreshLineage(payload.targetSlot);
  }

  if (payload.type === 'merge_complete') {
    lineage.markMerge(payload.sourceSlot, payload.targetSlot);
    refreshLineage(payload.targetSlot);
  }

  if (statuses[payload.type]) {
    setStatus(statuses[payload.type]);
    return true;
  }

  if (payload.type === 'bridge_error') {
    setStatus(`Error: ${payload.message}`);
    return true;
  }

  return false;
}

function handleMessage(payload) {
  if (handleLifecycleEvent(payload)) return;
  if (handleInstanceEvent(payload)) return;
  handleActionEvent(payload);
}

function boot() {
  ws = createSocket(
    handleMessage,
    () => setStatus('Connected'),
    () => setStatus('Disconnected'),
  );

  newInstanceBtn.addEventListener('click', () => {
    if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'create_instance' }));
  });
}

boot();
