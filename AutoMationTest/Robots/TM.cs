using System;
using System.Collections.Generic;
using System.Text;
using System.Threading;
using System.Net.Sockets;
using System.Net;
using System.IO;
using System.Diagnostics;

namespace AutoMationTest.Robots
{
    public class TM
    {


        private Thread m_ServerStart;

        private Socket serverSocket;
        private Socket clientSocket;

        public int port;
        public string ReceiveServerMSG = "";
        string StrRecieve = "";
        bool bManualStop = false;

        public void ServerStart()
        {

            while (true)
            {

                try
                {
                    //AddLog("Start");
                    //创建终结点
                    IPEndPoint localEndPoint = new IPEndPoint(IPAddress.Any, port);
                    //创建Socket
                    serverSocket = new Socket(localEndPoint.AddressFamily, SocketType.Stream, ProtocolType.Tcp);
                    //绑定端口
                    serverSocket.Bind(localEndPoint);
                    //监听
                    serverSocket.Listen(10);

                    //this.AddLog("Port " + port.ToString() + " Wait connect...");
                    this.clientSocket = serverSocket.Accept();

                    while (true)
                    {
                        try
                        {
                            if (clientSocket.Connected)
                            {

                                Robot.IsConnected = true;
                                byte[] arrMsgRec = new byte[1024 * 1024 * 2];
                                int length = clientSocket.Receive(arrMsgRec);
                                StrRecieve = System.Text.Encoding.ASCII.GetString(arrMsgRec, 0, length);
                                if (StrRecieve != "")
                                {
                                    //staObj.RevRobotMsg = StrRecieve;
                                    Robot.ReceiveMSG_From_Robot += StrRecieve;
                                    StrRecieve = "";
                                }
                                //Thread.Sleep(10);
                            }
                            else
                            {

                                Robot.IsConnected = false;
                                break;
                            }
                        }
                        catch (Exception ex)
                        {

                            Robot.IsConnected = false;
                            ex.ToString();
                            clientSocket.Close();
                            break;
                        }
                    }

                }
                catch (Exception)
                {
                    Robot.IsConnected = false;

                    if (!bManualStop)
                    {
                        #region Catch exception
                        //AddLog("手臂端已異常斷開連接，Server端嘗試恢復監聽");
                        if (this.clientSocket != null && clientSocket.Connected)
                        {
                            try { this.clientSocket.Disconnect(false); }
                            catch (Exception ex1) { }
                            //AddLog("Disconnect clientSocket");
                        }
                        if (this.clientSocket != null)
                        {
                            try
                            {
                                this.clientSocket.Close();
                                this.clientSocket = null;
                            }
                            catch (Exception ex2) { }

                            //AddLog("Close clientSocket");
                        }

                        if (this.serverSocket != null)
                        {
                            try
                            {
                                this.serverSocket.Close();
                                this.serverSocket = null;
                            }
                            catch (Exception ex3) { }

                            //AddLog("Close serverSocket");
                        }
                        //try
                        //{
                        //    if (m_ReceiveThread.IsAlive)
                        //    {
                        //        m_ReceiveThread.Abort();
                        //    }
                        //    m_ReceiveThread = null;

                        //}
                        //catch (Exception ex11) { }

                        //try
                        //{
                        //    if (m_CheckConnect.IsAlive)
                        //    {
                        //        m_CheckConnect.Abort();
                        //    }
                        //    m_CheckConnect = null;
                        //}
                        //catch (Exception ex22) { }

                        //try
                        //{
                        //    if (m_ServerStart.IsAlive)
                        //    {
                        //        m_ServerStart.Abort();
                        //    }
                        //}
                        //catch (Exception ex33) { }


                        //this.m_ServerStart = new Thread(new ThreadStart(this.ServerStart));
                        //this.m_ServerStart.Start();
                        #endregion

                        //Thread.Sleep(100);
                    }
                    else
                    {
                        //AddLog("手動斷開手臂連接");
                        break;
                    }
                }



            }
        }

        public void SendToRobot(string msg, bool ClearLastReceive)
        {
            if (clientSocket != null && clientSocket.Connected)
            {
                if (ClearLastReceive)
                    Robot.ReceiveMSG_From_Robot = "";

                this.clientSocket.Send(this.ParseStrToData(msg));

            }
          
        }

        private string ParseDataToStr(byte[] data)
        {
            return Encoding.UTF8.GetString(data);
        }
        private byte[] ParseStrToData(string str)
        {
            return Encoding.UTF8.GetBytes(str);
        }

        public void RobotConnect()
        {
            if (m_ServerStart == null)
            {
                this.m_ServerStart = new Thread(new ThreadStart(this.ServerStart));
                this.m_ServerStart.Start();
                bManualStop = false;
            }
            else
            {
                if (m_ServerStart.IsAlive)
                {
                    //AddLog("已連接");
                }
                else
                {

                    m_ServerStart = null;
                    this.m_ServerStart = new Thread(new ThreadStart(this.ServerStart));
                    this.m_ServerStart.Start();
                    bManualStop = false;
                }
            }


        }

        public void DisconnetRobot()
        {
            bManualStop = true;
            if (serverSocket != null)
            {
                serverSocket.Close();
                serverSocket = null;
            }
            if (clientSocket != null)
            {
                clientSocket.Close();
                clientSocket = null;
            }


            //AddLog("手動斷開手臂!");
        }

    }
}
