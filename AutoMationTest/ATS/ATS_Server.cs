using System;
using System.Collections.Generic;
using System.Text;
using System.Threading;
using System.Net.Sockets;
using System.Net;

namespace AutoMationTest.ATS
{
  /* 此類為 單站別 ATS端 使用；
   * 多站測試ATS請使用ADSServer（ATS端）和ALLATSUI（上位機端）搭配使用;
   * 本類功能：與上位機完成交互；
   * 使用方法：
   * WaitDUT()；
   * SendToServer(string msg)；
   * WaitServer(string msg)；
   * 
   */



    public class ATS_Server
    {
        private bool bPlaceDUTOK;
        public bool bReceiveBarcodeOK;
        public string Barcode;
        private string nowTime = "";
        AutoResetEvent Notice = new AutoResetEvent(true);
        private Thread m_ServerStart;
        private Socket serverSocket;
        private Socket clientSocket;
        private Thread m_ReceiveThread;
        private Thread m_CheckConnect;
        private bool getRev;
        //string Log_Path = "";
        int port;
        public string ReceiveServerMSG = "";
        public ATS_Server(int port)
        {
            this.port = port;

            this.m_ServerStart = new Thread(new ThreadStart(this.ServerStart));
            this.m_ServerStart.Start();
        }

        private void ServerStart()
        {
            try
            {

                //创建终结点
                IPEndPoint localEndPoint = new IPEndPoint(IPAddress.Any, port);
                //创建Socket
                serverSocket = new Socket(localEndPoint.AddressFamily, SocketType.Stream, ProtocolType.Tcp);
                //绑定端口
                serverSocket.Bind(localEndPoint);
                //监听
                serverSocket.Listen(10);

                this.clientSocket = serverSocket.Accept();

                if (this.clientSocket.Connected)
                {
                    //AddLog(clientSocket.RemoteEndPoint.ToString() + " Connect OK...");
                    this.m_ReceiveThread = new Thread(new ThreadStart(this.ReceiveThread));
                    this.m_ReceiveThread.Start();
                    this.m_CheckConnect = new Thread(new ThreadStart(CheckConnect));
                    this.m_CheckConnect.Start();
                }
            }
            catch (Exception)
            {

                if (this.clientSocket != null && clientSocket.Connected)
                {
                    this.clientSocket.Disconnect(false);

                }
                if (this.clientSocket != null)
                {
                    this.clientSocket.Close();
                    this.clientSocket = null;
                }

                if (this.serverSocket != null)
                {
                    this.serverSocket.Close();
                    this.serverSocket = null;

                }
                try
                {
                    if (m_ReceiveThread.IsAlive)
                    {
                        m_ReceiveThread.Abort();
                    }
                }
                catch (Exception ex1)
                {
                }

                try
                {
                    if (m_CheckConnect.IsAlive)
                    {
                        m_CheckConnect.Abort();
                    }
                }
                catch (Exception ex2)
                {
                }
                try
                {
                    if (m_ServerStart.IsAlive)
                    {
                        m_ServerStart.Abort();
                    }
                }
                catch (Exception ex3)
                {
                }
                this.m_ServerStart = new Thread(new ThreadStart(this.ServerStart));
                this.m_ServerStart.Start();
            }
        }

        private void CheckConnect()
        {
            while (true)
            {
                getRev = false;
                Thread.Sleep(4000);
                if (!getRev)
                {

                    if (this.clientSocket != null && clientSocket.Connected)
                    {
                        this.clientSocket.Disconnect(false);

                    }
                    if (this.clientSocket != null)
                    {
                        this.clientSocket.Close();
                        this.clientSocket = null;

                    }

                    if (this.serverSocket != null)
                    {
                        this.serverSocket.Close();
                        this.serverSocket = null;

                    }
                    try
                    {
                        if (m_ReceiveThread.IsAlive)
                        {
                            m_ReceiveThread.Abort();
                        }
                    }
                    catch (Exception ex1)
                    {
                    }
                    try
                    {
                        if (m_ServerStart.IsAlive)
                        {
                            m_ServerStart.Abort();
                        }
                    }
                    catch (Exception ex2)
                    {
                    }
                    this.m_ServerStart = new Thread(new ThreadStart(this.ServerStart));
                    this.m_ServerStart.Start();
                    break;
                }
            }
        }

        public void SendToServer(string msg)
        {
            if (clientSocket != null && clientSocket.Connected)
            {
                this.clientSocket.Send(this.ParseStrToData(msg + "_CEND"));
                //this.AddLog("發送：" + msg + "_CEND");
            }
            else
            {
                //this.AddLog("已斷開與上位機連接，無法發送：" + msg + "_CEND");
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
        public void WaitDUT()
        {
            bPlaceDUTOK = false;
            while (true)
            {
                if (bPlaceDUTOK)
                {
                    break;
                }
                else
                {
                    Thread.Sleep(50);
                }
            }
        }

        public void WaitServer(string msg)
        {

            while (true)
            {
                if (ReceiveServerMSG.Contains(msg))
                {
                    break;
                }
                else
                {
                    Thread.Sleep(50);
                }
            }
        }

        private void ReceiveThread()
        {
            StringBuilder sb = new StringBuilder();
            string terminateString = "_CEND";
            int receiveBufferSize = 1024;
            byte[] buffer = new byte[receiveBufferSize];  //buffer大小，此处为1024
            int receivedSize = 0;
            string rawMsg = "";
            int rnFixLength = terminateString.Length;   //这个是指消息结束符的长度，此处为\r\n
            string myReceive = "";
            string name = "";
            string barcode = "";
            while (this.clientSocket.Connected)
            {
                try
                {
                    receivedSize = this.clientSocket.Receive(buffer);
                    rawMsg = System.Text.Encoding.UTF8.GetString(buffer, 0, receivedSize);
                    for (int i = 0; i < rawMsg.Length; )               //遍历接收到的整个buffer文本
                    {
                        if (i <= rawMsg.Length - rnFixLength)
                        {
                            if (rawMsg.Substring(i, rnFixLength) != terminateString)//非消息结束符，则加入sb
                            {
                                sb.Append(rawMsg[i]);
                                i++;
                            }
                            else
                            {
                                myReceive = sb.ToString();


                                if (!myReceive.Contains("aaa"))
                                {
                                    ReceiveServerMSG = myReceive;

                                    //this.AddLog("接受：" + myReceive);
                                    this.clientSocket.Send(this.ParseStrToData(myReceive + "ok_CEND"));
                                    //this.AddLog("發送:" + myReceive + "ok_CEND");
                                }

                                if (myReceive.Contains("test"))
                                {
                                    bPlaceDUTOK = true;
                                }
                                else if (myReceive.Contains("aaa"))
                                {
                                    getRev = true;
                                }

                                else if (myReceive.Contains("B1=") || myReceive.Contains("B2=") || myReceive.Contains("B3=") || myReceive.Contains("B4="))
                                {
                                    try
                                    {
                                        //this.AddLog("接受：" + myReceive);
                                        name = myReceive.Split('=')[0];
                                        barcode = myReceive.Split('=')[1];
                                        //AddLog("Name:" + name);
                                        //AddLog("Barcode:" + barcode);
                                        bReceiveBarcodeOK = true;
                                        this.Barcode = barcode;
                                    }
                                    catch (Exception e)
                                    {
                                        //AddLog(e.ToString());
                                    }
                                }
                                sb.Remove(0, sb.Length);
                                i += rnFixLength;
                            }
                        }
                        else
                        {
                            sb.Append(rawMsg[i]);
                            i++;
                        }
                    }
                    Thread.Sleep(10);
                }
                catch (Exception e)
                {

                }
            }
        }
    }
}
