import { normalizedPoint, intensity } from './spatial'
import { test, expect } from 'vitest'

test.each([ [640,360], [320,180], [180,320], [1000,1000] ])('responsive normalized coordinates at %s × %s',(width,height)=>{
  expect(normalizedPoint(20+width*.25,30+height*.75,{left:20,top:30,width,height})).toEqual({x:.25,y:.75})
  expect(normalizedPoint(20+width,30+height,{left:20,top:30,width,height})).toEqual({x:1,y:1})
})
test('empty bounds and clipping',()=>{
  expect(normalizedPoint(0,0,{left:0,top:0,width:0,height:2})).toBeNull()
  expect(normalizedPoint(-10,40,{left:0,top:0,width:10,height:20})).toEqual({x:0,y:1})
})
test('intensity is derived without modifying counts',()=>{
  expect(intensity(0,0)).toBe(0);expect(intensity(3,6)).toBe(.5);expect(intensity(6,6)).toBe(1)
})
