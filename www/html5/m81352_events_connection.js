import {M81337Connection} from './m81337_connection.js';
import {encodeEventsRequest} from './m81352_events_protocol.js';

export const createEventsState = () => ({revision: 0, views: [], last: null, error: '', loadedAt: 0});

/** events-v1: server-built ActivityTemplate views (list) and committed actions (act). */
export class M81352Connection extends M81337Connection {
  emptyState() { return {...super.emptyState(), events: createEventsState()}; }
  withOutside(snapshot) {
    return {...super.withOutside(snapshot), events: this.cachedView('events', this.state.events, structuredClone)};
  }
  /** The lobby renders before GATE reaches 'ready' (and again after a
   * reconnect); load the event bar the moment the connection is usable. */
  phase(name, message) {
    const before = this.state?.phase;
    super.phase(name, message);
    if (name === 'ready' && before !== 'ready') queueMicrotask(() => this.eventsList().catch(() => {}));
  }
  setEvents(values) {
    const previous = this.state.events || createEventsState();
    this.state.events = {...previous, ...values, revision: previous.revision + 1};
    this.update();
  }
  async eventsRequest(action, values = {}) {
    if (this.state.phase !== 'ready' || !this.gate) throw new Error('Hãy chờ kết nối hoàn tất.');
    const gate = this.gate, generation = this.generation, request_id = globalThis.crypto.randomUUID().replace(/-/g, '');
    const packet = await this.request(gate, encodeEventsRequest(action, request_id, values),
      p => p.type === 'eventsReply' && p.reply.request_id === request_id, 'xác nhận sự kiện', 15000);
    if (generation !== this.generation) return null;
    const reply = packet.reply;
    if (!reply.ok) {
      this.setEvents({error: reply.error?.message || 'Máy chủ từ chối thao tác sự kiện.'});
      const error = new Error(reply.error?.message || 'Máy chủ từ chối thao tác sự kiện.'); error.code = reply.error?.code; throw error;
    }
    this.setEvents({views: reply.events || [], last: reply.result || this.state.events.last, error: '', loadedAt: Date.now()});
    return reply;
  }
  /** Refresh only: does not occupy the shared busy lock. */
  eventsList() { return this.eventsRequest('list'); }
  eventsAct(event, op, key = '') {
    return this.action('events', ['lobby'], () => this.eventsRequest('act', {event, op, key}));
  }
}
