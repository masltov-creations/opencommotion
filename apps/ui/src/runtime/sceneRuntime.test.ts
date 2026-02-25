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

  it('supports render, fx, material, camera, and environment primitives', () => {
    const scene = buildScene(
      [
        { op: 'replace', path: '/render/mode', at_ms: 0, value: '3d' },
        { op: 'add', path: '/fx/bubble_emitter', at_ms: 20, value: { type: 'bubble_emitter', count: 10 } },
        { op: 'add', path: '/charts/segmented_attach', at_ms: 25, value: { type: 'bar-segmented', segments: [] } },
        { op: 'replace', path: '/materials/fish_bowl_glass', at_ms: 30, value: { shader_id: 'glass_refraction_like' } },
        { op: 'replace', path: '/camera/motion', at_ms: 40, value: { mode: 'glide-orbit' } },
        { op: 'replace', path: '/environment/mood', at_ms: 50, value: { phase: 'day-to-dusk' } },
      ],
      100,
    )

    expect(scene.render.mode).toBe('3d')
    expect(scene.fx.bubble_emitter.type).toBe('bubble_emitter')
    expect(scene.charts.segmented_attach.type).toBe('bar-segmented')
    expect(scene.materials.fish_bowl_glass.shader_id).toBe('glass_refraction_like')
    expect(scene.camera.motion).toEqual({ mode: 'glide-orbit' })
    expect(scene.environment.mood).toEqual({ phase: 'day-to-dusk' })
  })

  it('supports lyric-word patches for timed captions', () => {
    const scene = buildScene(
      [
        {
          op: 'replace',
          path: '/lyrics/words',
          at_ms: 300,
          value: {
            items: [
              { text: 'The', at_ms: 300 },
              { text: 'cow', at_ms: 720 },
            ],
            start_ms: 300,
            step_ms: 420,
          },
        },
      ],
      1000,
    )
    expect(scene.lyrics.words.length).toBe(2)
    expect(scene.lyrics.words[1].text).toBe('cow')
    expect(scene.lyrics.step_ms).toBe(420)
  })
})
