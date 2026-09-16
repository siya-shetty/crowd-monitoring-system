import type { Point } from '../services/apiClient'

/** Use the actual aspect-matched SVG bounds, never the surrounding card. */
export function normalizedPoint(clientX:number, clientY:number, bounds:{left:number;top:number;width:number;height:number}):Point|null {
  if (bounds.width <= 0 || bounds.height <= 0) return null
  return {x:Math.min(1,Math.max(0,(clientX-bounds.left)/bounds.width)),y:Math.min(1,Math.max(0,(clientY-bounds.top)/bounds.height))}
}

export function intensity(count:number, maximum:number):number { return maximum > 0 ? count / maximum : 0 }
