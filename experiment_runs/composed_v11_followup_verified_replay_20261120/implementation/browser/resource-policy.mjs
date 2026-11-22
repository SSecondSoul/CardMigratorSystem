// No network permission expansion: decode bounded passive inline images and
// respond from memory. SVG is deliberately a small drawing-only grammar.
export const resourcePolicy='bounded_passive_inline_images_v1'
export function inlineImage(url,type,method='GET') {
  if (type!=='image' || method!=='GET' || typeof url!=='string' || url.length>262144) return null
  const m=/^data:(image\/(?:png|jpeg|gif|webp|svg\+xml));base64,([A-Za-z0-9+/]+={0,2})$/.exec(url)
  if (!m || m[2].length%4) return null
  const body=Buffer.from(m[2],'base64')
  if (!body.length || body.length>196608 || body.toString('base64')!==m[2]) return null
  if (m[1]==='image/svg+xml') {
    if (body.length>16384) return null
    const text=body.toString('utf8'), stack=[], tags=new Set(['svg','g','path','rect','circle','ellipse','line','polyline','polygon'])
    const attrs=new Set(['xmlns','width','height','viewBox','fill','fill-rule','stroke','stroke-width','stroke-linecap',
      'stroke-linejoin','stroke-dasharray','opacity','fill-opacity','stroke-opacity','d','x','y','x1','y1','x2','y2','cx','cy','r','rx','ry','points','transform'])
    if (!text.startsWith('<svg ') || /[&]|<!|<\?|url\s*\(|\\|[\u0000-\u0008]/i.test(text)) return null
    let at=0, roots=0
    const pattern=/<(\/?)([A-Za-z][\w-]*)([^<>]*?)(\/?)>/g
    for (const token of text.matchAll(pattern)) {
      if (text.slice(at,token.index).trim() || !tags.has(token[2])) return null
      at=token.index+token[0].length
      if (token[1]) {if (token[3].trim() || token[4] || stack.pop()!==token[2]) return null; continue}
      if (!stack.length && (token[2]!=='svg' || ++roots!==1)) return null
      let rest=token[3], seen=new Set()
      while (rest.trim()) {
        const a=/^\s+([\w-]+)\s*=\s*(["'])(.*?)\2/s.exec(rest)
        if (!a || !attrs.has(a[1]) || seen.has(a[1])) return null
        seen.add(a[1]);rest=rest.slice(a[0].length)
        if (a[1]==='xmlns') {if (a[3]!=='http://www.w3.org/2000/svg') return null}
        else if (!/^[A-Za-z0-9\s.,%()+#:\-]*$/.test(a[3]) || /(?:https?:|data:|javascript:)/i.test(a[3])) return null
      }
      if (!token[4]) stack.push(token[2])
    }
    if (text.slice(at).trim() || stack.length || roots!==1) return null
  } else {
    // Reject mislabeled HTML/SVG; use fixed image signatures, not extension.
    const ok=m[1]==='image/png'?body.subarray(0,8).equals(Buffer.from([137,80,78,71,13,10,26,10])):
      m[1]==='image/jpeg'?body[0]===255&&body[1]===216&&body[2]===255:
      m[1]==='image/gif'?/^GIF8[79]a$/.test(body.subarray(0,6).toString('ascii')):
      body.subarray(0,4).toString('ascii')==='RIFF'&&body.subarray(8,12).toString('ascii')==='WEBP'
    if (!ok) return null
  }
  return {contentType:m[1],body}
}
