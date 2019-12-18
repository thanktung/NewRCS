using System;
using System.Collections.Generic;
using System.Text;
using System.Net.Sockets;
using System.Threading;
using System.Net;
using AutoMationTest.Common;
using AutoMationTest.UI;
using System.Collections;

namespace AutoMationTest.ATS
{
  /* 此類為 單站別 上位機端 使用；
   * 多站測試ATS請使用ADSServer（ATS端）和ALLATSUI（上位機端）搭配使用;
   * 本類功能：與ATS完成交互；
   * 使用方法：
   * StartATS()；
   * SendToATS(string cmd)；
   * ReceiveMSG；
   * WaitATS(string msg);
   */

    public class SendATSClient
    {
        private Socket ClientSocket;
        private string IP;
        private int Port;
        private Thread ReceiveServerThread; //持續接收Server msg線程
        private Thread HeartBeatThread;
        IPEndPoint RemoteEP;

        public string ReceiveMSG = "";

        public SendATSClient(string IP, int Port)
        {
            this.IP = IP;
            this.Port = Port;
            ClientSocket = new Socket(AddressFamily.InterNetwork, SocketType.Stream, ProtocolType.Tcp);
            RemoteEP = new IPEndPoint(IPAddress.Parse(IP), Port);
        }
        public void ConnectServer()
        {
            try
            {

                ClientSocket = new Socket(AddressFamily.InterNetwork, SocketType.Stream, ProtocolType.Tcp);
                RemoteEP = new IPEndPoint(IPAddress.Parse(IP), Port);
                ClientSocket.Connect(RemoteEP);
                if (ClientSocket.Connected)
                {
                    ReceiveServerThread = new Thread(new ThreadStart(ReceiveServer));
                    ReceiveServerThread.Start();
                    HeartBeatThread = new Thread(new ThreadStart(HeartBeat));
                    HeartBeatThread.Start();
                }
            }
            catch (Exception)
            {
                this.DisConnectServer();
            }
        }
        public void DisConnectServer()
        {

            if (ClientSocket.Connected)
            {
                if (ReceiveServerThread.IsAlive)
                {
                    ReceiveServerThread.Abort();
                }

                if (HeartBeatThread.IsAlive)
                {
                    HeartBeatThread.Abort();
                }
                this.ClientSocket.Shutdown(SocketShutdown.Both);
                this.ClientSocket.Disconnect(false);
            }
        }
        public bool isConnected()
        {
            return ClientSocket.Connected;
        }
        public void ReceiveServer()
        {
            StringBuilder sb = new StringBuilder();
            string terminateString = "_CEND";
            int receiveBufferSize = 1024;
            byte[] buffer = new byte[receiveBufferSize];  //buffer大小，此处为1024
            int receivedSize = 0;
            string rawMsg = "";
            int rnFixLength = terminateString.Length;   //这个是指消息结束符的长度，此处为\r\n
            while (this.ClientSocket.Connected)
            {
                try
                {
                    receivedSize = this.ClientSocket.Receive(buffer);
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
                                string MyReceive = sb.ToString();

                                ReceiveMSG = MyReceive;

                                //if (MyReceive.Contains("OK"))
                                //{
                                //    Program.form1.AddServerLog("[ATS]Send OK");
                                //}
                                //else if (MyReceive.Contains("SMTError"))
                                //{
                                //    Program.form1.AddServerLog("Send SMT Error");

                                //}
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
                    Thread.Sleep(100);
                }
                catch (Exception e)
                {
                }
            }
        }
        public void SendToATS(string cmd)
        {
            this.ClientSocket.Send(ParseStrToData(cmd + "_CEND"));
        }

        public void StartATS()
        {
            SendToATS("test");
        }

        public void WaitATS(string msg)
        {

            while (true)
            {
                if (ReceiveMSG.Contains(msg))
                {
                    break;
                }
                else
                {
                    Thread.Sleep(50);
                }
            }
        }

        public void HeartBeat()
        {
            try
            {
                while (this.ClientSocket.Connected)
                {

                    Thread.Sleep(100);      //delay時間不要太短，會造成隊列擁堵
                    this.ClientSocket.Send(ParseStrToData("aaa_CEND"));
                }
            }
            catch (Exception ee)
            {
                //Program.form1.AddLog(ee.ToString());
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
    }
}
