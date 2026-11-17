'use strict';
// Reserved source API write policy, not a simulated Vue internal instance.
const INSTANCE_FIELDS = new Set(('uid vnode type parent appContext root next subTree effect update job scope render proxy exposed exposeProxy withProxy provides ids accessCache renderCache components directives propsOptions emitsOptions emit emitted propsDefaults inheritAttrs ctx data props attrs slots refs setupState setupContext suspense suspenseId asyncDep asyncResolved isMounted isUnmounted isDeactivated bc c bm m bu u um bum da a rtg rtc ec sp').split(' '));
class PrototypeCapabilityError extends Error {
  constructor(capability) {
    super('San business instance does not implement: ' + capability);
    this.name = 'PrototypeCapabilityError';
    this.code = 'san_business_capability_unsupported';
    this.capability = capability;
  }
}
module.exports = {INSTANCE_FIELDS, PrototypeCapabilityError};
