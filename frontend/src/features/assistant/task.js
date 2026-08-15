const TASK_TYPES = new Set(['registration', 'payment', 'records'])
const TASK_FIELDS = ['title', 'scheduleId', 'chargeId', 'recordId']

export function toTask(task) {
  if (!task || !TASK_TYPES.has(task.type)) return null
  const nextTask = { type: task.type }
  TASK_FIELDS.forEach((field) => {
    if (typeof task[field] === 'string' || typeof task[field] === 'number') nextTask[field] = task[field]
  })
  return nextTask
}
