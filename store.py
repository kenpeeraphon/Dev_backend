import http.server
import urllib.parse
import json
import os
import datetime

try:
    import qrcode
except ImportError:  # pragma: no cover - optional dependency
    qrcode = None

DB_FILE = 'store.json'
QR_DIR = 'qrcodes'

class Store:
    def __init__(self, db_file=DB_FILE):
        self.db_file = db_file
        self.load()

    def load(self):
        if os.path.exists(self.db_file):
            with open(self.db_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.inventory = data.get('inventory', {})
            self.sales = data.get('sales', [])
            self.purchases = data.get('purchases', [])
            self.next_id = data.get('next_id', 1)
        else:
            self.inventory = {}
            self.sales = []
            self.purchases = []
            self.next_id = 1

    def save(self):
        with open(self.db_file, 'w', encoding='utf-8') as f:
            json.dump({
                'inventory': self.inventory,
                'sales': self.sales,
                'purchases': self.purchases,
                'next_id': self.next_id,
            }, f)

    def add_item(self, name, price, cost, quantity):
        item_id = str(self.next_id)
        self.next_id += 1
        self.inventory[item_id] = {
            'name': name,
            'price': price,
            'cost': cost,
            'quantity': quantity
        }
        self.purchases.append({
            'item_id': item_id,
            'quantity': quantity,
            'expense': cost * quantity,
            'timestamp': datetime.datetime.utcnow().isoformat()
        })
        self.save()
        if qrcode:
            self.generate_qrcode(item_id)
        return item_id

    def sell_item(self, item_id, quantity):
        if item_id not in self.inventory:
            raise KeyError('Item not found')
        item = self.inventory[item_id]
        if quantity > item['quantity']:
            raise ValueError('Not enough stock')
        item['quantity'] -= quantity
        self.sales.append({
            'item_id': item_id,
            'quantity': quantity,
            'revenue': quantity * item['price'],
            'timestamp': datetime.datetime.utcnow().isoformat()
        })
        self.save()

    def summary(self):
        revenue = sum(s['revenue'] for s in self.sales)
        expense = sum(p['expense'] for p in self.purchases)
        return {
            'revenue': revenue,
            'expense': expense,
            'profit': revenue - expense,
        }

    def generate_qrcode(self, item_id):
        if not qrcode:
            return None
        item = self.inventory.get(item_id)
        if not item:
            return None
        qr = qrcode.QRCode(box_size=4, border=2)
        qr.add_data(f"{item_id}:{item['name']}")
        img = qr.make_image(fill_color='black', back_color='white')
        os.makedirs(QR_DIR, exist_ok=True)
        path = os.path.join(QR_DIR, f"{item_id}.png")
        img.save(path)
        return path

store = Store()

class StoreHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == '/':
            self.show_inventory()
        elif parsed.path == '/summary':
            self.show_summary()
        elif parsed.path == '/qrcode':
            self.show_qrcode(parsed.query)
        else:
            super().do_GET()

    def do_POST(self):
        if self.path == '/add':
            self.handle_add()
        elif self.path == '/sell':
            self.handle_sell()
        else:
            self.send_error(404, 'Unknown path')

    def parse_post(self):
        length = int(self.headers.get('Content-Length', '0'))
        data = self.rfile.read(length)
        return urllib.parse.parse_qs(data.decode())

    def handle_add(self):
        fields = self.parse_post()
        name = fields.get('name', [''])[0]
        price = float(fields.get('price', ['0'])[0])
        cost = float(fields.get('cost', ['0'])[0])
        qty = int(fields.get('quantity', ['0'])[0])
        if name and qty > 0:
            store.add_item(name, price, cost, qty)
        self.redirect('/')

    def handle_sell(self):
        fields = self.parse_post()
        item_id = fields.get('id', [''])[0]
        qty = int(fields.get('quantity', ['0'])[0])
        try:
            if qty > 0:
                store.sell_item(item_id, qty)
        except (KeyError, ValueError):
            pass
        self.redirect('/')

    def show_inventory(self):
        rows = []
        for item_id, item in store.inventory.items():
            rows.append(f"<tr><td>{item_id}</td><td>{item['name']}</td>"\
                        f"<td>{item['price']}</td><td>{item['quantity']}</td>"\
                        f"<td><a href='/qrcode?id={item_id}'>QR</a></td></tr>")
        body = "\n".join(rows)
        html = f"""<html><body>
        <h1>Inventory</h1>
        <table border='1'>
        <tr><th>ID</th><th>Name</th><th>Price</th><th>Qty</th><th>QR</th></tr>
        {body}
        </table>
        <h2>Add Item</h2>
        <form method='post' action='/add'>
            Name: <input name='name'><br>
            Price: <input name='price' type='number' step='0.01'><br>
            Cost: <input name='cost' type='number' step='0.01'><br>
            Quantity: <input name='quantity' type='number'><br>
            <input type='submit' value='Add'>
        </form>
        <h2>Sell Item</h2>
        <form method='post' action='/sell'>
            ID: <input name='id'><br>
            Quantity: <input name='quantity' type='number'><br>
            <input type='submit' value='Sell'>
        </form>
        <p><a href='/summary'>Summary</a></p>
        </body></html>"""
        self.send_html(html)

    def show_summary(self):
        data = store.summary()
        html = f"""<html><body>
        <h1>Summary</h1>
        <p>Revenue: {data['revenue']}</p>
        <p>Expense: {data['expense']}</p>
        <p>Profit: {data['profit']}</p>
        <p><a href='/'>Back</a></p>
        </body></html>"""
        self.send_html(html)

    def show_qrcode(self, query):
        params = urllib.parse.parse_qs(query)
        item_id = params.get('id', [''])[0]
        path = os.path.join(QR_DIR, f"{item_id}.png")
        if qrcode and os.path.exists(path):
            with open(path, 'rb') as f:
                img = f.read()
            self.send_response(200)
            self.send_header('Content-Type', 'image/png')
            self.send_header('Content-Length', str(len(img)))
            self.end_headers()
            self.wfile.write(img)
        else:
            self.send_error(404, 'QR code unavailable')

    def send_html(self, html):
        data = html.encode()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def redirect(self, path):
        self.send_response(302)
        self.send_header('Location', path)
        self.end_headers()


def run(server_class=http.server.HTTPServer, handler_class=StoreHandler, port=8000):
    server = server_class(('', port), handler_class)
    print(f"Serving on http://localhost:{port}")
    server.serve_forever()

if __name__ == '__main__':
    run()
