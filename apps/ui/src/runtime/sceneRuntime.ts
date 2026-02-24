export type Patch = {
  op: 'add' | 'replace' | 'remove'
  path: string
  value?: unknown
  at_ms?: number
}

export type SceneActor = {
  type: string
  x?: number
  y?: number
  animation?: { name: string; duration_ms: number; easing: string }
  motion?: string | { name: string; duration_ms: number; beam?: boolean }
  radius?: number
}

export type SceneState = {
  actors: Record<string, SceneActor>
  charts: Record<string, { type: string; points?: number[][]; slices?: Array<{ label: string; value: number }> }>
  annotations: Array<{ text: string; style: string }>
  scene: { transition?: { name: string; duration_ms: number; easing: string } }
}

export const emptyScene: SceneState = {
  actors: {},
  charts: {},
  annotations: [],
  scene: {},
}

function parsePath(path: string): string[] {
  return path.split('/').filter(Boolean)
}

function cloneScene(scene: SceneState): SceneState {
  return {
    actors: { ...scene.actors },
    charts: { ...scene.charts },
    annotations: [...scene.annotations],
    scene: { ...scene.scene },
  }
}

export function applyPatch(scene: SceneState, patch: Patch): SceneState {
  const next = cloneScene(scene)
  const parts = parsePath(patch.path)

  if (parts[0] === 'actors' && parts.length >= 2) {
    const actorId = parts[1]
    if (patch.op === 'remove') {
      delete next.actors[actorId]
      return next
    }

    if (parts.length === 2) {
      next.actors[actorId] = {
        ...(next.actors[actorId] || {}),
        ...(patch.value as Record<string, unknown>),
      } as SceneActor
      return next
    }

    if (parts[2] === 'animation') {
      next.actors[actorId] = {
        ...(next.actors[actorId] || {}),
        animation: patch.value as SceneActor['animation'],
      }
      return next
    }

    if (parts[2] === 'motion') {
      next.actors[actorId] = {
        ...(next.actors[actorId] || {}),
        motion: patch.value as SceneActor['motion'],
      }
      return next
    }
  }

  if (parts[0] === 'charts' && parts.length === 2) {
    const chartId = parts[1]
    if (patch.op === 'remove') {
      delete next.charts[chartId]
      return next
    }
    next.charts[chartId] = patch.value as SceneState['charts'][string]
    return next
  }

  if (parts[0] === 'annotations') {
    if (patch.op === 'add') {
      next.annotations.push(patch.value as { text: string; style: string })
      return next
    }
    if (patch.op === 'remove' && next.annotations.length) {
      next.annotations.pop()
      return next
    }
  }

  if (parts[0] === 'scene' && parts[1] === 'transition') {
    if (patch.op === 'remove') {
      delete next.scene.transition
      return next
    }
    next.scene.transition = patch.value as SceneState['scene']['transition']
    return next
  }

  return next
}

export function buildScene(patches: Patch[], playbackMs: number): SceneState {
  const ordered = [...patches].sort((a, b) => (a.at_ms || 0) - (b.at_ms || 0))
  return ordered.reduce((state, patch) => {
    if ((patch.at_ms || 0) > playbackMs) {
      return state
    }
    return applyPatch(state, patch)
  }, emptyScene)
}
