using System;
using System.Collections.Generic;
using System.Text;
using System.Threading;
using System.Net.Sockets;
using System.Net;

namespace AutoMationTest.Function.Net
{
    public class SocketServer
    {

        private Thread m_ServerStart;
        private Socket serverSocket;
        private Socket clientSocket;

        public int port;
        string StrRecieve = "";
        bool bManualStop = false;
        public bool IsConnected = false;
        public string ReceiveMSG = "";

        public SocketServer(int nPort)
        {
            this.port = nPort;
        }


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

                                IsConnected = true;
                                byte[] arrMsgRec = new byte[1024 * 1024 * 2];
                                int length = clientSocket.Receive(arrMsgRec);
                                StrRecieve = System.Text.Encoding.ASCII.GetString(arrMsgRec, 0, length);
                                if (StrRecieve != "")
                                {

                                    ReceiveMSG = StrRecieve;
                                    StrRecieve = "";
                                }
                            }
                            else
                            {

                                IsConnected = false;
                                break;
                            }
                        }
                        catch (Exception ex)
                        {

                            IsConnected = false;
                            ex.ToString();
                            clientSocket.Close();
                            break;
                        }
                    }

                }
                catch (Exception)
                {
                    IsConnected = false;

                    if (!bManualStop)
                    {
                        #region Catch exception

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

                        #endregion


                    }
                    else
                    {

                        break;
                    }
                }

            }
        }




        public void SendToClient(string msg)
        {
            if (clientSocket != null && clientSocket.Connected)
            {
                this.clientSocket.Send(this.ParseStrToData(msg));
            }
            else
            {

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


        public void Connect()
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

        public void Disconnet()
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

        }


    }
}
