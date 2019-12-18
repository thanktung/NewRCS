using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Net;
using System.Net.Sockets;
using System.Drawing;
using System.IO;
using System.Threading;

namespace RobotMainForm
{
    public class RemoteControl
    {
        string pro = "{0}&{1}&{2}&{3}&{4}";//我的软件的协传输议
        string userName = Dns.GetHostName();// 获取我的主机名
        IPAddress ip;//我的ip
        int port = 9305;//我的端口号
        Thread th;
        bool bQuite = false;
        Socket server;
        public bool bConnected = false;
        public RemoteControl()
        {
            #region //****************初始化用户信息
            string hostName = Dns.GetHostName();
            IPAddress[] ips = Dns.GetHostAddresses(hostName);
            foreach (IPAddress item in ips)
            {
                if (!item.IsIPv6LinkLocal && item.ToString().Contains("10.15"))
                {
                    ip = item;
                }
            }

            #endregion //*********************************
        }
        //public bool IsConnected()
        //{
        //    try
        //    {
        //        return server.Connected;
        //    }
        //    catch (Exception ex)
        //    {
        //        return false;
        //    }
        //}


        public void UdpSendMsg(IPAddress sendIp, string cmdNo, string msg)
        {
            try
            {
                Socket client = new Socket(AddressFamily.InterNetwork,
                    SocketType.Dgram, ProtocolType.Udp);
                //发送的内容
                string context = string.Format(pro, userName,
                     ip.ToString(), DateTime.Now.Ticks, cmdNo, msg);
                byte[] buffer = Encoding.Default.GetBytes(context);
                //发给谁
                client.Connect(sendIp, port);
                //发送
                client.Send(buffer);
                client.Close();
            }
            catch (Exception ex)
            {

            }
        }


        public void ReciveData()
        {
            try
            {
                IPAddress ip = IPAddress.Any;
                server = new Socket(AddressFamily.InterNetwork,
                   SocketType.Dgram, ProtocolType.Udp);
                EndPoint ipe = new IPEndPoint(ip, port);
                server.Bind(ipe);
                byte[] buffer = new byte[60000];
                //int width=Screen.PrimaryScreen .Bounds .Width;
                //int height=Screen.PrimaryScreen.Bounds.Height;
                while (true)
                {
                    //if (server.Connected)
                    //{
                    // Bitmap bmp = new Bitmap(width, height);
                    MemoryStream ms = new MemoryStream();
                    int len = server.Receive(buffer);
                    ms.Write(buffer, 0, len);
                    while (true)
                    {
                        if (len == 1 && buffer[0] == 100)
                        {
                            break;
                        }
                        len = server.Receive(buffer);
                        ms.Write(buffer, 0, len);
                    }
                    //流里面存放了一个图片的所有字节
                    Bitmap bmp = new Bitmap(ms);
                    Program.mainform.SetPicbox(Program.mainform.pbox_Remote, bmp);
                    //}
                    //else
                    //{
                    //    break;
                    //}
                    bConnected = true;

                    if (bQuite)
                    {
                        bConnected = false;
                        break;
                    }
                }
            }
            catch (Exception ex)
            {
                bConnected = false;
            }

        }

        public void Connect()
        {
            bQuite = false;
            th = new Thread(new ThreadStart(ReciveData));
            th.IsBackground = true;
            th.Start();
        }

        public void Close()
        {
            bQuite = true;

            if (server != null)
            {
                try
                {
                    server.Close();
                    server.Dispose();
                    server = null;
                }
                catch (Exception ex)
                { }
            }

            if (th != null)
            {
                if (th.IsAlive)
                {
                    th.Abort();
                }
            }


        }
    }
}
