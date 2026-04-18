export class LineageStore {
  constructor() {
    this.records = new Map();
  }

  ensure(slot) {
    if (!this.records.has(slot)) {
      this.records.set(slot, {
        slot,
        agentUuid: null,
        parentSlot: null,
        rootSlot: slot,
        mergedFrom: [],
        forkPoint: null,
      });
    }
    return this.records.get(slot);
  }

  setAgent(slot, agentUuid) {
    const record = this.ensure(slot);
    record.agentUuid = agentUuid;
    return record;
  }

  markFork(sourceSlot, targetSlot, forkPoint = null) {
    const source = this.ensure(sourceSlot);
    const target = this.ensure(targetSlot);
    target.parentSlot = sourceSlot;
    target.rootSlot = source.rootSlot ?? sourceSlot;
    target.forkPoint = forkPoint || target.forkPoint || null;
    return target;
  }

  markMerge(sourceSlot, targetSlot) {
    const target = this.ensure(targetSlot);
    if (!target.mergedFrom.includes(sourceSlot)) {
      target.mergedFrom.push(sourceSlot);
    }
    return target;
  }

  setForkPoint(slot, forkPoint) {
    const record = this.ensure(slot);
    record.forkPoint = forkPoint || null;
    return record;
  }

  remove(slot) {
    this.records.delete(slot);
  }

  get(slot) {
    return this.records.get(slot) || null;
  }

  format(slot) {
    const record = this.get(slot);
    if (!record) return ['root: self', 'parent: —', 'merged: —'];

    const root = record.rootSlot === slot || record.rootSlot == null
      ? 'self'
      : `instance ${record.rootSlot + 1}`;
    const parent = record.parentSlot == null
      ? '—'
      : `instance ${record.parentSlot + 1}`;
    const merged = record.mergedFrom.length === 0
      ? '—'
      : record.mergedFrom.map((value) => `instance ${value + 1}`).join(', ');

    const forkHead = record.forkPoint?.git?.shortHead || '—';
    const forkStat = record.forkPoint?.git?.shortStat || '—';
    const changedFiles = record.forkPoint?.git?.changedFiles?.length ?? 0;
    const totalTokens = record.forkPoint?.contextUsage?.totalTokens ?? null;
    const assistantMessages = record.forkPoint?.contextUsage?.assistantMessages ?? null;

    return [
      `root: ${root}`,
      `parent: ${parent}`,
      `merged: ${merged}`,
      `fork head: ${forkHead}`,
      `fork diff: ${forkStat} (${changedFiles} files)`,
      `fork ctx: ${totalTokens == null ? '—' : `${totalTokens} tok / ${assistantMessages} asst`}`,
    ];
  }
}
