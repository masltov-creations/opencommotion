import { describe, expect, it } from 'vitest'

import { applyPatch, buildScene, emptyScene, type Patch } from './sceneRuntime'

describe('sceneRuntime', () => {
  it('applies actor and chart patches deterministically by time', () => {
    const scene = buildScene(
      [
        { op: 'add', path: '/charts/adoption_curve', at_ms: 200, value: { type: 'line', points: [[0, 0], [100, 100]] } },
        { op: 'add', path: '/actors/guide', at_ms: 0, value: { type: 'character', x: 120, y: 180 } },
      ],
      500,
    )

    expect(scene.actors.guide.type).toBe('character')
    expect(scene.charts.adoption_curve.type).toBe('line')
  })

  it('keeps patch apply median under baseline threshold', () => {
    const patches: Patch[] = []
    for (let idx = 0; idx < 1600; idx += 1) {
      patches.push({
        op: 'add',
        path: `/actors/a-${idx}`,
        at_ms: idx,
        value: { type: 'character', x: idx % 400, y: idx % 240 },
      })
    }

    const samples: number[] = []
    for (let run = 0; run < 7; run += 1) {
      const started = performance.now()
      const scene = buildScene(patches, 2000)
      const elapsed = performance.now() - started
      samples.push(elapsed)
      expect(Object.keys(scene.actors).length).toBeGreaterThan(0)
    }

    const sorted = [...samples].sort((a, b) => a - b)
    const median = sorted[Math.floor(sorted.length / 2)]
    expect(median).toBeLessThan(450)
  })

  it('removes actor when remove patch is applied', () => {
    const withActor = applyPatch(emptyScene, {
      op: 'add',
      path: '/actors/guide',
      value: { type: 'character', x: 10, y: 10 },
    })
    const removed = applyPatch(withActor, { op: 'remove', path: '/actors/guide' })
    expect(removed.actors.guide).toBeUndefined()
  })
})
