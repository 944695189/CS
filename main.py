import asyncio
import logging
from http.server import HTTPServer
import tornado.escape
import tornado.options
import tornado.web
import tornado.websocket
import os.path
import socket
import serial
import serial.tools.list_ports
import time
from tornado.options import define, options
import tornado.ioloop
import json
import pymysql.cursors
from tornado.web import RequestHandler
check = -1
flag = 5
route = -1

Instroments = dict()
CommBusBusy = 0

CommPort = "COM4"  #
bps = 100000  # 超时设置
timex = 10
define("port", default=8880, help="run on the given port", type=int)
db =pymysql.connect(
    host='localhost',
    user='root',
    password='321524446x',
    database='signup',
)


def do_command(ch):
    #9 : ; < = > ? @   A B C
    if ch == '10':
        ch = ':'
    elif ch == '11':
        ch = ';'
    elif ch == '12':
        ch = '<'
    elif ch == '13':
        ch = '='
    elif ch == '14':
        ch = '>'

    try:
        b_cmd = bytes(str(ch), encoding='utf-8')
        ser.write(b_cmd)
    except Exception as e:
        print("--do_command--异常-：", e)

    if ch == '0':
       pass
# 串口检测
def comport_check():
    lst = {}
    # 检测所有存在的串口，将信息存储在字典中
    port_list = list(serial.tools.list_ports.comports())
    for port in port_list:
        lst["%s" % port[0]] = "%s" % port[1]

    return lst


class Application(tornado.web.Application):
    def __init__(self):
        handlers = [(r"/", MainHandler),
                (r"/chatsocket", ChatSocketHandler),
                ]
        settings = dict(
            cookie_secret="__TODO:_GENERATE_YOUR_OWN_RANDOM_VALUE_HERE__",
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            xsrf_cookies=False,
        )
        super().__init__(handlers, **settings)

class MainHandler(tornado.web.RequestHandler):

    def get(self):
        f = open('main.html', 'r', encoding='utf-8').read()
        ip = socket.gethostbyname(socket.gethostname())
        nws = 'ws://' + ip + ':8880/chatsocket'
        f = f.replace('<!--V WebSocketIP_Port -->', nws)
        self.write(f)

class ChatSocketHandler(tornado.websocket.WebSocketHandler):
    waiters = set()#等待连接的客户端
    monitors = set()#监控客户端
    instroments = {}#仪器数据
    cache = []#消息缓存
    cache_size = 200#设置消息缓存大小为200



    def open(self):#在WebSocket 连接建立时调用，初始化实例属性
        #print("ChatSocketHandler open")
        self.idNum = None
        self.status = 'waiter'
        for instro in ChatSocketHandler.instroments:#遍历仪器信息
            print(instro)
        ChatSocketHandler.waiters.add(self)

    def on_close(self):
        print("close")
        ser.write(b'0O')
        ChatSocketHandler.waiters.remove(self)

    @classmethod
    def update_cache(cls, chat):
        cls.cache.append(chat)
        if len(cls.cache) > cls.cache_size:
            cls.cache = cls.cache[-cls.cache_size:]#超过缓存大小则保留最近消息

    @classmethod
    def send_updates(cls, chat):
        logging.info("sending message to %d waiters", len(cls.waiters))
        for waiter in cls.waiters:#循环遍历所有等待连接的客户端
            try:
                waiter.write_message(chat)
            except:
                logging.error("Error sending message", exc_info=True)

    @classmethod
    def update_data(cls, key, data):
        busy = False
        try:
            busy = ChatSocketHandler.instroments[key]['busy']#获取单片机数据
        except:
            pass

        ChatSocketHandler.instroments[key] = data
        ChatSocketHandler.instroments[key]['busy'] = busy

        for waiter in cls.waiters:
            if waiter.idNum == key:
                print('update_data', waiter.idNum)
            try:
                data['msgType'] = 'set'  #  set  chat
                waiter.write_message(data)
           #     print(data)
            except:
                logging.error("Error sending message", exc_info=True)

    def on_message(self, message):  # 处理前端发送的信息

        logging.info("got message %r", message)
        message = eval(message)#消息字符串转换为 Python 对象
        print(message)
        judge = 10
        global route, check, flag

        for cmd in message:
            print(cmd,message[cmd])
            if cmd == 'line':
                 do_command(message[cmd])
            elif cmd == 'PWM':
                 do_command(message[cmd])

        ChatSocketHandler.update_cache(cmd)
        ChatSocketHandler.send_updates(cmd)
commbuffer = b''
t0 = time.time()
comm_idle = True
def check_com_data():#持续地监视串口数据的变化，执行操作

    def update_commdata(bs):
        try:
            s = bs.decode('GBK')
        except Exception as e:
            print(bs,e)
            pass

        es = '{"' + s.replace('=','":"').replace(', ','","')  +'"}'
        eds=eval(es)

        if isinstance(eds, dict):#type(eds).__name__ == 'dict':
            k = 'idNum'+ eds['idNum']
            ChatSocketHandler.update_data(k,eds)
        else:
            print(eds)
            pass

    def do_cmd(bcmd):
        if comm_idle:
            ser.write(bcmd)

    global  commbuffer, ser, t0
    global  Instroments

    try:
        if ser.isOpen():
            inwait = ser.in_waiting
            if inwait >0:
                commbuffer += ser.read(inwait)
                sk = commbuffer.find(b'\n')
                if sk != -1:
                    bs = commbuffer[0:sk].strip()
                    do_cmd(b'm')
                    commbuffer = commbuffer[sk+1:]
                    update_commdata(bs)
                    t0 = time.time()

            else:
                t1 = time.time()-t0
                if t1>3.0:
                    print('check_com_data: no response time: ', t1)
                    do_cmd(b'm')
                    t0 = time.time()

        else:
            ser.open()
            print('check_com_data: OpenCommPort--')
    except Exception as e:
        print('check_com_data:COM is ----',e)
        cp = comport_check()
        if CommPort in cp:
            try:
                ser = serial.Serial(CommPort, bps)  # 控制继电器切换电路
            except Exception as e:
                print('check_com_data: COM is ----', e)
        return

class RegisterHandler(RequestHandler):
    def get(self):
        self.render('signup.html')

    def post(self):
        username = self.get_argument('username', default=None)
        email = self.get_argument('email', default=None)
        password = self.get_argument('password', default=None)
        confirm_password = self.get_argument('confirm_password', default=None)

        if not username or not email or not password or not confirm_password:
            self.write(json.dumps({'message': 'Please fill in all the fields.'}))
            return

        if password != confirm_password:
            self.write(json.dumps({'message': 'Passwords do not match.'}))
            return

        cursor = db.cursor()
        try:
            cursor.execute(
                "INSERT INTO signup.account (username, email, password) VALUES (%(username)s, %(email)s, %(password)s)",
                {'username': username, 'email': email, 'password': password})

            db.commit()
            self.redirect("/login")
        except Exception as e:#捕获try块中出现的异常
            db.rollback()
            print('Registration failed with error:', e)
            self.write(json.dumps({'message': 'Registration failed. Please try again later.'}))
        cursor.close()

class LoginHandler(RequestHandler):
    def get(self):
        self.render('login.html')

    def post(self):
        try:
            username = self.get_argument('username', default=None)
            password = self.get_argument('password', default=None)
            cursor = db.cursor()
            cursor.execute("SELECT * FROM signup.account WHERE username=%(username)s AND password=%(password)s",
                           {'username': username, 'password': password})
            user = cursor.fetchone()
            cursor.close()

            if user:
                self.set_cookie('username', username)
                self.redirect("/success")
            else:
                self.write(json.dumps({'message': 'Invalid username or password.'}))
        except Exception as e:
            print("Error:", e)
            self.write(json.dumps({'message': 'An error occurred during login.'}))






class SuccessHandler(RequestHandler):
    async def async_main(self):
        # 在 Tornado 的事件循环中异步执行 main() 函数
        tornado.ioloop.IOLoop.current().spawn_callback(main)
    async def get(self):
        # 处理 GET 请求，并调用 async_main() 方法

        await self.async_main()

        self.redirect(f"http://{ip}:{options.port}/") #进入socket（IP+端口），
async def main():
    #test()
    # app.stop()#释放app占用的端口给app2使用
    tornado.options.parse_command_line()

    app2=Application()

    app2.listen(options.port)

    tornado.ioloop.PeriodicCallback(check_com_data,100).start()  #100ms
    await asyncio.Event().wait()

if __name__ == "__main__":
    app = tornado.web.Application([
        (r"/", LoginHandler),  # 标记
        (r'/register', RegisterHandler),
        (r'/login', LoginHandler),
        (r"/success", SuccessHandler),
        (r"/css/(.*)", tornado.web.StaticFileHandler, {"path": "css"}),
        (r"/css/(.*)", tornado.web.StaticFileHandler, {"path": "img"}),
    ], debug=True)
    try:
        ser = serial.Serial(CommPort, bps)  # 控制继电器切换电路
    except Exception as e:
        print('check_com_data:COM is ----', e)
    ip = socket.gethostbyname(socket.gethostname()) # 或者您的服务器 IP 地址
    # 输出服务器地址和端口号
    portc=options.port+8
    print(f"Server is running at http://{ip}:{portc}/")
    app = tornado.httpserver.HTTPServer(app)
    app.listen(portc)
    tornado.ioloop.IOLoop.current().start()
    print(comport_check())


