export function cameraError(error:unknown):string {
  const name=typeof error==='object'&&error!==null&&'name' in error?String(error.name):''
  return ({NotAllowedError:'Camera permission denied. Allow camera access in your browser settings.',NotFoundError:'No camera device was found.',NotReadableError:'Camera is unavailable or already in use by another application.',OverconstrainedError:'Camera does not support the requested capture settings.'} as Record<string,string>)[name]??'Unable to start the camera. Check device access and try again.'
}
