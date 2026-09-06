#!/usr/bin/env node
// server.mjs — frame receiver + static server for the browser-render channel.
//
//   node server.mjs <serveDir> <framesDir> [port]
//
// POST /frame  → raw PNG body streamed straight to <framesDir>/<X-Frame-Name>
// GET  /*      → static files from <serveDir> (templates)
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';

const serveDir = path.resolve(process.argv[2]);
const framesDir = path.resolve(process.argv[3]);
const port = parseInt(process.argv[4] || '8739', 10);
fs.mkdirSync(framesDir, { recursive: true });

const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.png': 'image/png' };

http.createServer((req, res) => {
  if (req.method === 'POST' && req.url === '/frame') {
    const name = req.headers['x-frame-name'] || `f${Date.now()}.png`;
    const out = fs.createWriteStream(path.join(framesDir, name));
    req.pipe(out); // raw binary → disk, zero re-encoding
    req.on('end', () => { res.writeHead(200, { 'Access-Control-Allow-Origin': '*' }); res.end('ok'); });
    req.on('error', () => { res.writeHead(500); res.end('err'); });
    return;
  }
  if (req.method === 'OPTIONS') {
    res.writeHead(204, {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'POST, GET, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, X-Frame-Name',
    });
    return res.end();
  }
  const rel = decodeURIComponent(req.url.split('?')[0]);
  const file = path.join(serveDir, rel === '/' ? 'doodle.html' : rel);
  if (!file.startsWith(serveDir) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) {
    res.writeHead(404); return res.end('nf');
  }
  res.writeHead(200, { 'Content-Type': MIME[path.extname(file)] || 'application/octet-stream' });
  res.end(fs.readFileSync(file));
}).listen(port, () => console.log(`serving ${serveDir} on :${port}, frames -> ${framesDir}`));
