using System;
using System.Collections.Generic;
//using System.Linq;
using System.Text;
using System.Threading;
using System.Net.Sockets;
using System.Net;
using System.Windows.Forms;
using System.Timers;
using System.IO;

namespace AutoMationTest.Robots
{
    public class Epson
    {
        public string IP;
        public int SystemPort;
        public int UserPort;
        public int UserPort2;
        public string LoginPassword;
        public bool RobotConnected = false;
        private bool bmanualstop = false;
        System.Timers.Timer timer_TcpControl;

        #region RobotConnect & RobotAction
        public void RobotConnect(bool buseuser2)
        {
            bmanualstop = false;

            thread_RobotServer = new Thread(RobotServer_Start);
            thread_RobotServer.IsBackground = true;
            thread_RobotServer.Start();

            thread_RobotClient = new Thread(RobotClient_Start);
            thread_RobotClient.IsBackground = true;
            thread_RobotClient.Start();

            if (buseuser2)
            {
                thread_RobotClient2 = new Thread(RobotClient2_Start);
                thread_RobotClient2.IsBackground = true;
                thread_RobotClient2.Start();
            }
        }
        public bool bsocketOK = false;
        private string Str;
        private string StrRecieve;
        private string StrRecieve2;
        Thread thread_RobotServer;
        Thread thread_RobotClient;
        Thread thread_RobotClient2;
        public static Socket serverSocket;
        public static Socket clientSocket;
        public static Socket clientSocket2;
        void timer1_Tick(Object sender, ElapsedEventArgs e)
        {
            send("$GetStatus");
        }

        private void getstatus()
        {
            while (true)
            {
                send("$GetStatus");
                Thread.Sleep(1000);
            }
        }

        private void RobotServer_Start()
        {
            //timer_TcpControl = new System.Timers.Timer(1000);
            //timer_TcpControl.Elapsed += new ElapsedEventHandler(timer1_Tick);
            //timer_TcpControl.AutoReset = true;

            Thread getthd = new Thread(new ThreadStart(getstatus));
            getthd.Start();

            while (true)
            {
                try
                {

                    IPAddress ipaddress = IPAddress.Parse(IP);
                    IPEndPoint ipendpoint = new IPEndPoint(ipaddress, SystemPort);
                    serverSocket = new Socket(AddressFamily.InterNetwork, SocketType.Stream, ProtocolType.Tcp);
                    serverSocket.Connect(ipendpoint);

                    //ResetRobot();
                }
                catch (Exception ex)
                {
                    serverSocket.Dispose();
                    //MessageBox.Show("server start: " + ex.ToString());
                    if (bmanualstop)
                    {
                        return;
                    }
                    Thread.Sleep(100);
                    continue;
                }

                while (true)
                {
                    try
                    {
                        byte[] ReceiveByte = new byte[1024 * 1024 * 2];
                        int length = serverSocket.Receive(ReceiveByte);
                        Str = Encoding.ASCII.GetString(ReceiveByte, 0, length);
                        System.Threading.Thread.Sleep(100);
                    }
                    catch (Exception ex)
                    {
                        //MessageBox.Show("server : " + ex.ToString());
                        ex.ToString();
                        serverSocket.Close();
                        serverSocket.Dispose();
                        Thread.Sleep(100);
                        if (bmanualstop)
                        {
                            return;
                        }
                        break;
                    }
                }
            }
        }

        private void RobotClient_Start()
        {
            while (true)
            {
                try
                {
                    Robot.IsConnected = false;
                    IPAddress address = IPAddress.Parse(IP);
                    IPEndPoint endpoint = new IPEndPoint(address, UserPort);
                    clientSocket = new Socket(AddressFamily.InterNetwork, SocketType.Stream, ProtocolType.Tcp);
                    clientSocket.Connect(endpoint);
                }
                catch (Exception ex)
                {

                    Robot.IsConnected = false;
                    //MessageBox.Show("start ex:" + Robot.IsConnected.ToString());
                    clientSocket.Dispose();

                    //MessageBox.Show("clent start: "+ex.ToString());
                    if (bmanualstop)
                    {
                        return;
                    }
                    Thread.Sleep(100);
                    //File.AppendAllText("debug.txt", DateTime.Now.ToString("yyyyMMdd-HHmmss") + " client start ex:" + ex.ToString() + "\r\n");
                    continue;
                }

                while (true)
                {
                    try
                    {
                        if (clientSocket.Connected)
                        {
                            if (!bepsonstop)
                            {
                                Robot.IsConnected = true;
                            }
                            else
                            {
                                Robot.IsConnected = false;
                            }
                            byte[] arrMsgRec = new byte[1024 * 1024 * 2];
                            int length = clientSocket.Receive(arrMsgRec);
                            StrRecieve = System.Text.Encoding.ASCII.GetString(arrMsgRec, 0, length);
                            if (StrRecieve != "")
                            {
                                //staObj.RevRobotMsg = StrRecieve;
                                Robot.ReceiveMSG_From_Robot += StrRecieve;
                                StrRecieve = "";
                            }

                            System.Threading.Thread.Sleep(100);
                        }
                        else
                        {
                            //MessageBox.Show("Client Unconnect");
                            //File.AppendAllText("debug.txt", DateTime.Now.ToString("yyyyMMdd-HHmmss") + " client not connect\r\n");
                            bsocketOK = false;
                            Robot.IsConnected = false;
                            Thread.Sleep(100);
                            if (bmanualstop)
                            {
                                return;
                            }
                            break;
                        }
                    }
                    catch (Exception ex)
                    {
                        //MessageBox.Show("Client :"+ex.ToString());

                        bsocketOK = false;
                        Robot.IsConnected = false;
                        //MessageBox.Show("start ex:" + ex.Message);

                        clientSocket.Close();
                        clientSocket.Dispose();
                        Thread.Sleep(100);
                        //File.AppendAllText("debug.txt", DateTime.Now.ToString("yyyyMMdd-HHmmss") + " client connect ex:" + ex.ToString() + "\r\n");
                        if (bmanualstop)
                        {
                            return;
                        }
                        break;
                    }


                }
            }
        }

        private void RobotClient2_Start()
        {
            while (true)
            {
                try
                {

                    IPAddress address = IPAddress.Parse(IP);
                    IPEndPoint endpoint = new IPEndPoint(address, UserPort2);
                    clientSocket2 = new Socket(AddressFamily.InterNetwork, SocketType.Stream, ProtocolType.Tcp);
                    clientSocket2.Connect(endpoint);
                }
                catch (Exception ex)
                {
                    clientSocket2.Dispose();
                    //MessageBox.Show("clent start: "+ex.ToString());
                    if (bmanualstop)
                    {
                        return;
                    }
                    Thread.Sleep(100);
                    continue;
                }

                while (true)
                {
                    try
                    {
                        if (clientSocket2.Connected)
                        {

                            Thread.Sleep(100);
                        }
                        else
                        {

                            bsocketOK = false;
                            Robot.IsConnected = false;
                            Thread.Sleep(100);
                            if (bmanualstop)
                            {
                                return;
                            }
                            break;
                        }
                    }
                    catch (Exception ex)
                    {
                        //MessageBox.Show("Client :"+ex.ToString());

                        bsocketOK = false;
                        Robot.IsConnected = false;
                        ex.ToString();
                        clientSocket2.Close();
                        clientSocket2.Dispose();
                        Thread.Sleep(100);
                        if (bmanualstop)
                        {
                            return;
                        }
                        break;
                    }
                }
            }
        }

        public void Send202(string cmd)
        {
            try
            {

                if (clientSocket2.Connected)
                {
                    Byte[] sendByte = new Byte[128];
                    string sendToServer = cmd + "\r\n";
                    sendByte = Encoding.ASCII.GetBytes(sendToServer.ToCharArray());
                    clientSocket2.Send(sendByte, sendByte.Length, 0);

                }
            }
            catch (Exception ex)
            { }
        }

        public void SendCheck202(string cmd, string checkmsg, ref string sreceive)
        {
            try
            {
                sreceive = "";
                if (clientSocket2.Connected)
                {
                    Byte[] sendByte = new Byte[128];
                    string sendToServer = cmd + "\r\n";
                    sendByte = Encoding.ASCII.GetBytes(sendToServer.ToCharArray());
                    clientSocket2.Send(sendByte, sendByte.Length, 0);
                    for (int i = 0; i < 100; i++)
                    {
                        Thread.Sleep(10);
                        byte[] arrMsgRec = new byte[1024 * 1024 * 2];
                        int length = clientSocket2.Receive(arrMsgRec);
                        sreceive = System.Text.Encoding.ASCII.GetString(arrMsgRec, 0, length);
                        if (sreceive.Contains(checkmsg))
                        {
                            break;
                        }
                    }
                }
            }
            catch (Exception ex)
            { }
        }

        public void send(string Msg)
        {
            try
            {

                Byte[] sendByte = new Byte[128];
                string sendToServer = Msg + "\r\n";
                sendByte = Encoding.ASCII.GetBytes(sendToServer.ToCharArray());
                serverSocket.Send(sendByte, sendByte.Length, 0);
            }
            catch (Exception ex)
            { }
        }

        public void SendMsg(string str, bool ClearLast)
        {
            try
            {
                if (ClearLast)
                    Robot.ReceiveMSG_From_Robot = "";
                if (clientSocket.Connected)
                {
                    Byte[] sendByte = new Byte[128];
                    string sendToServer = str + "\r\n";
                    sendByte = Encoding.ASCII.GetBytes(sendToServer.ToCharArray());
                    clientSocket.Send(sendByte, sendByte.Length, 0);
                }
            }
            catch (Exception ex)
            {
                File.AppendAllText("debug.txt", DateTime.Now.ToString("yyyyMMdd-HHmmss") + " client send ex:" + ex.ToString() + "\r\n");
                //MessageBox.Show(ex.Message);
                //clientSocket.Close();
            }
        }

        public void ResetRobot()
        {

            send("$Login," + LoginPassword);
            Thread.Sleep(300);
            send("$SetMotorsOff,0");
            Thread.Sleep(300);
            send("$Stop,0");
            Thread.Sleep(300);
            send("$Reset,0");
            Thread.Sleep(300);
            send("$SetMotorsOn,0");
            Thread.Sleep(300);
            send("$Start,0");
            Thread.Sleep(300);

            bepsonstop = false;

        }
        bool bepsonstop = false;
        public void DisConnectRobot()
        {
            send("$SetMotorsOff,0");
            Thread.Sleep(300);
            send("$Stop,0");
            Thread.Sleep(300);
            send("$Reset,0");
            Thread.Sleep(300);
            bepsonstop = true;
            Robot.IsConnected = false;
        }

        #endregion



        public void Close()
        {
            bmanualstop = true;
            try
            {
                serverSocket.Close();
            }
            catch (Exception ex1) { };
            try
            {
                clientSocket.Close();
            }
            catch (Exception ex2) { };
        }


    }
}
