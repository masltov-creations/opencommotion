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
  style?: Record<string, unknown>
  animation?: { name: string; duration_ms: number; easing: string }
  motion?: string | { name: string; duration_ms?: number; beam?: boolean; [key: string]: unknown }
  radius?: number
}

export type SceneState = {
  actors: Record<string, SceneActor>
  charts: Record<
    string,
    {
      type: string
      points?: number[][]
      slices?: Array<{ label: string; value: number }>
      segments?: Array<{ label: string; target: number; color?: string }>
      trend?: string
      at_ms?: number
      duration_ms?: number
      [key: string]: unknown
    }
  >
  fx: Record<string, { type: string; [key: string]: unknown }>
  materials: Record<string, { shader_id: string; fallback?: boolean; [key: string]: unknown }>
  environment: Record<string, unknown>
  camera: Record<string, unknown>
  render: { mode?: '2d' | '3d' }
  lyrics: { words: Array<{ text: string; at_ms: number }>; start_ms?: number; step_ms?: number }
  annotations: Array<{ text: string; style: string }>
  scene: { transition?: { name: string; duration_ms: number; easing: string } }
}

export const emptyScene: SceneState = {
  actors: {},
  charts: {},
  fx: {},
  materials: {},
  environment: {},
  camera: {},
  render: {},
  lyrics: { words: [] },
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
    fx: { ...scene.fx },
    materials: { ...scene.materials },
    environment: { ...scene.environment },
    camera: { ...scene.camera },
    render: { ...scene.render },
    lyrics: { ...scene.lyrics, words: [...scene.lyrics.words] },
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

  if (parts[0] === 'fx' && parts.length === 2) {
    const fxId = parts[1]
    if (patch.op === 'remove') {
      delete next.fx[fxId]
      return next
    }
    next.fx[fxId] = patch.value as SceneState['fx'][string]
    return next
  }

  if (parts[0] === 'materials' && parts.length === 2) {
    const materialId = parts[1]
    if (patch.op === 'remove') {
      delete next.materials[materialId]
      return next
    }
    next.materials[materialId] = patch.value as SceneState['materials'][string]
    return next
  }

  if (parts[0] === 'environment') {
    if (parts.length === 1) {
      if (patch.op === 'remove') {
        next.environment = {}
      } else if (patch.value && typeof patch.value === 'object') {
        next.environment = {
          ...next.environment,
          ...(patch.value as Record<string, unknown>),
        }
      }
      return next
    }
    if (parts.length === 2) {
      if (patch.op === 'remove') {
        delete next.environment[parts[1]]
      } else {
        next.environment[parts[1]] = patch.value as unknown
      }
      return next
    }
  }

  if (parts[0] === 'camera') {
    if (parts.length === 1) {
      if (patch.op === 'remove') {
        next.camera = {}
      } else if (patch.value && typeof patch.value === 'object') {
        next.camera = {
          ...next.camera,
          ...(patch.value as Record<string, unknown>),
        }
      }
      return next
    }
    if (parts.length === 2) {
      if (patch.op === 'remove') {
        delete next.camera[parts[1]]
      } else {
        next.camera[parts[1]] = patch.value as unknown
      }
      return next
    }
  }

  if (parts[0] === 'render' && parts.length === 2) {
    if (patch.op === 'remove') {
      delete next.render[parts[1] as keyof SceneState['render']]
      return next
    }
    next.render[parts[1] as keyof SceneState['render']] = patch.value as SceneState['render']['mode']
    return next
  }

  if (parts[0] === 'lyrics' && parts[1] === 'words') {
    if (patch.op === 'remove') {
      next.lyrics = { words: [] }
      return next
    }
    const value = patch.value as { items?: Array<{ text: string; at_ms: number }>; start_ms?: number; step_ms?: number }
    const items = Array.isArray(value?.items) ? value.items : []
    next.lyrics = {
      words: items.map((row) => ({ text: String(row.text || ''), at_ms: Number(row.at_ms || 0) })),
      start_ms: Number(value?.start_ms || 0),
      step_ms: Number(value?.step_ms || 0),
    }
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
