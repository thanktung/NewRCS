using System;
using System.Collections.Generic;
using System.Text;
using System.Net;
using System.Threading;
using System.Net.Sockets;

namespace AutoMationTest.ATS
{
    /* 此類為 多站別-測試站 ATS端 使用；
     * 單站ATS請使用ATS_Server（ATS端）和ATS_Client（上位機端）搭配使用
     * 本類功能：與上位機完成交互；
     * 使用方法：
     * WaitDUT()；
     * SendBarcode(string barcode)；
     * SendPass()；
     * SendNG(string NGItem, string Value)；
     * SendWarning(string warning)；
     * 
     */


    public class ADSServer
    {
        private bool bPlaceDUTOK;
        public bool bReceiveBarcodeOK;
        public string Barcode;
        //private string nowTime = "";
        AutoResetEvent Notice = new AutoResetEvent(true);
        private Thread m_ServerStart;
        private Socket serverSocket;
        private Socket clientSocket;
        private Thread m_ReceiveThread;
        private Thread m_CheckConnect;
        private bool getRev;
        //string Log_Path = "";
        int port;
        public ADSServer(int port)
        {
            this.port = port;
            this.m_ServerStart = new Thread(new ThreadStart(this.ServerStart));
            this.m_ServerStart.Start();
        }

        private void ServerStart()
        {
            try
            {
                AddLog("Start");
                //创建终结点
                IPEndPoint localEndPoint = new IPEndPoint(IPAddress.Any, port);
                //创建Socket
                serverSocket = new Socket(localEndPoint.AddressFamily, SocketType.Stream, ProtocolType.Tcp);
                //绑定端口
                serverSocket.Bind(localEndPoint);
                //监听
                serverSocket.Listen(10);

                this.AddLog("Port " + port.ToString() + " Wait connect...");
                this.clientSocket = serverSocket.Accept();

                if (this.clientSocket.Connected)
                {
                    AddLog(clientSocket.RemoteEndPoint.ToString() + " Connect OK...");
                    this.m_ReceiveThread = new Thread(new ThreadStart(this.ReceiveThread));
                    this.m_ReceiveThread.Start();
                    this.m_CheckConnect = new Thread(new ThreadStart(CheckConnect));
                    this.m_CheckConnect.Start();
                }
            }
            catch (Exception)
            {
                AddLog("客戶端已異常斷開連接，Server端嘗試恢復監聽");
                if (this.clientSocket != null && clientSocket.Connected)
                {
                    this.clientSocket.Disconnect(false);
                    AddLog("Disconnect clientSocket");
                }
                if (this.clientSocket != null)
                {
                    this.clientSocket.Close();
                    this.clientSocket = null;
                    AddLog("Close clientSocket");
                }

                if (this.serverSocket != null)
                {
                    this.serverSocket.Close();
                    this.serverSocket = null;
                    AddLog("Close serverSocket");
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
                    AddLog("無法偵測心跳包，上位機斷開連接");
                    if (this.clientSocket != null && clientSocket.Connected)
                    {
                        this.clientSocket.Disconnect(false);
                        AddLog("Disconnect clientSocket");
                    }
                    if (this.clientSocket != null)
                    {
                        this.clientSocket.Close();
                        this.clientSocket = null;
                        AddLog("Close clientSocket");
                    }

                    if (this.serverSocket != null)
                    {
                        this.serverSocket.Close();
                        this.serverSocket = null;
                        AddLog("Close serverSocket");
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
        private void AddLog(string log)
        {
            //Notice.WaitOne();
            //nowTime = DateTime.Now.ToString("yyyyMMdd-HHmmss.fff ");
            //log = nowTime + " " + log;
            //log = log.TrimEnd('\0');
            //log = log + "\r\n";
            //File.AppendAllText(Log_Path, log);
            //Notice.Set();
        }


        public void SendPass()
        {
            if (clientSocket != null && clientSocket.Connected)
            {
                this.clientSocket.Send(this.ParseStrToData("TtoC_resultPass_CEND"));
                this.AddLog("發送：" + "TtoC_resultPass");
            }
            else
            {
                this.AddLog("已斷開與上位機連接，無法發送：" + "TtoC_resultPass");
            }
        }
        public void SendNG(string NGItem, string Value)
        {
            if (clientSocket != null && clientSocket.Connected)
            {
                this.clientSocket.Send(ParseStrToData("TtoC_resultNG" + "+" + NGItem + "+" + Value + "_CEND"));
                this.AddLog("發送：" + "TtoC_resultNG" + "+" + NGItem + "+" + Value);
            }
            else
            {
                this.AddLog("已斷開與上位機連接，無法發送：" + "TtoC_resultNG" + "+" + NGItem + "+" + Value);
            }
        }
        public void SendWarning(string warning)
        {
            if (clientSocket != null && clientSocket.Connected)
            {
                this.clientSocket.Send(ParseStrToData("TtoC_resultWarning" + "+" + warning + "_CEND"));
                this.AddLog("發送：" + "TtoC_resultWarning" + "+" + warning);
            }
            else
            {
                this.AddLog("已斷開與上位機連接，無法發送：" + "TtoC_resultWarning" + "+" + warning);
            }
        }
        public void SendBarcode(string barcode)
        {
            if (clientSocket != null && clientSocket.Connected)
            {
                this.clientSocket.Send(ParseStrToData("TtoC_barcode" + "+" + barcode + "_CEND"));
                this.AddLog("發送：" + "TtoC_barcode" + "+" + barcode);
            }
            else
            {
                this.AddLog("已斷開與上位機連接，無法發送：" + "TtoC_barcode" + "+" + barcode);
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
                    AddLog("放板OK");
                    break;
                }
                else
                {
                    Thread.Sleep(100);
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
                                if (myReceive.Contains("CtoT_placeDUTOK"))
                                {
                                    this.AddLog("接受：" + myReceive);
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
                                        this.AddLog("接受：" + myReceive);
                                        name = myReceive.Split('=')[0];
                                        barcode = myReceive.Split('=')[1];
                                        AddLog("Name:" + name);
                                        AddLog("Barcode:" + barcode);
                                        bReceiveBarcodeOK = true;
                                        this.Barcode = barcode;
                                    }
                                    catch (Exception e)
                                    {
                                        AddLog(e.ToString());
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
