from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from sys import argv
from EvacAttackModel import EvacAttackModel
import json

class Server(BaseHTTPRequestHandler):
    def _set_headers(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        
    def do_HEAD(self):
        self._set_headers()

    def do_POST(self):
        # refuse to receive non-json content
        if self.headers.get('content-type') != 'application/json':
            self.send_response(400)
            self.end_headers()
            return

        length = int(self.headers.get('content-length'))
        message = json.loads(self.rfile.read(length))
        if "Level" in message:
            model.override = message
        if "step" in message:
            model.step()
        
        self._set_headers()
        self.wfile.write(json.dumps(model.bim).encode("utf-8"))

def run(server_class=ThreadingHTTPServer, handler_class=Server, port=8008):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    
    print('Starting httpd on port %d...' % port)
    httpd.serve_forever()
    

if len(argv) == 3:
    with open(argv[1]) as f:
        j = json.load(f)
    model = EvacAttackModel(j)
    model.moving.set_density(0.5)
    model.moving.set_people_by_density()
    run(port=int(argv[2]))
else:
    print("File name and port needed")
    print('Test: curl --data "{\"step\":\"True\"}" --header "Content-Type: application/json" http://localhost:8008')
   
        
