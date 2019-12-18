using System;
using System.Collections.Generic;
using System.Text;
using System.Threading;
using System.Net.Sockets;
using System.Net;

namespace AutoMationTest.Function.Net
{
    public class SocketClient
    {
        public string IP;
        public int Port;
        public static Socket clientSocket;
        string StrRecieve = "";
        bool bmanualstop = false;
        public bool IsConnected = false;
        public string ReceiveMsg = "";
        Thread thread_Server;


        public SocketClient(string sIP, int nPort)
        {
            this.IP = sIP;
            this.Port = nPort;
        }

        private void Client_Start()
        {
            while (true)
            {
                try
                {

                    IPAddress address = IPAddress.Parse(IP);
                    IPEndPoint endpoint = new IPEndPoint(address, Port);
                    clientSocket = new Socket(AddressFamily.InterNetwork, SocketType.Stream, ProtocolType.Tcp);
                    clientSocket.Connect(endpoint);
                }
                catch (Exception ex)
                {
                    ex.ToString();
                    if (bmanualstop)
                    {
                        return;
                    }
                    Thread.Sleep(1000);
                    continue;
                }

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
                                ReceiveMsg = StrRecieve;
                                StrRecieve = "";
                            }
                        }
                        else
                        {

                            IsConnected = false;
                            if (bmanualstop)
                            {
                                return;
                            }
                            break;
                        }
                    }
                    catch (Exception ex)
                    {
                        IsConnected = false;
                        ex.ToString();
                        clientSocket.Close();
                        if (bmanualstop)
                        {
                            return;
                        }
                        break;
                    }
                }
            }
        }

        public void ConnectServer()
        {
            if (thread_Server == null)
            {
                bmanualstop = false;
                thread_Server = new Thread(Client_Start);
                thread_Server.IsBackground = true;
                thread_Server.Start();
            }
            else
            {
                if (thread_Server.IsAlive)
                {
                }
                else
                {
                    bmanualstop = false;
                    thread_Server = new Thread(Client_Start);
                    thread_Server.IsBackground = true;
                    thread_Server.Start();
                }
            }
        }

        public void SendMsg(string str)
        {
            try
            {
                Byte[] sendByte = new Byte[128];
                string sendToServer = str;
                sendByte = Encoding.ASCII.GetBytes(sendToServer.ToCharArray());
                clientSocket.Send(sendByte, sendByte.Length, 0);

            }
            catch (Exception ex)
            {

            }
        }

        public void DisconnectServer()
        {
            bmanualstop = true;
            try
            {
                clientSocket.Close();
            }
            catch (Exception ex1) { };
        }

    }
}
