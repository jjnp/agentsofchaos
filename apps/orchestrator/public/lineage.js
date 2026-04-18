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
      });
    }
    return this.records.get(slot);
  }

  setAgent(slot, agentUuid) {
    const record = this.ensure(slot);
    record.agentUuid = agentUuid;
    return record;
  }

  markFork(sourceSlot, targetSlot) {
    const source = this.ensure(sourceSlot);
    const target = this.ensure(targetSlot);
    target.parentSlot = sourceSlot;
    target.rootSlot = source.rootSlot ?? sourceSlot;
    return target;
  }

  markMerge(sourceSlot, targetSlot) {
    const target = this.ensure(targetSlot);
    if (!target.mergedFrom.includes(sourceSlot)) {
      target.mergedFrom.push(sourceSlot);
    }
    return target;
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

    return [
      `root: ${root}`,
      `parent: ${parent}`,
      `merged: ${merged}`,
    ];
  }
}
