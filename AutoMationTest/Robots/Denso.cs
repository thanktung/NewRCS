using System;
using System.Collections.Generic;
using System.Text;
using System.Net;
using System.Net.Sockets;
using System.Threading;

namespace AutoMationTest.Robots
{
    public class Denso
    {

        public string IP;
        public int Port;
        public static Socket clientSocket;
        string StrRecieve = "";
        bool bmanualstop = false;

        Thread thread_RobotServer;



        private void RobotClient_Start()
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
                            //RobotConnected = true;
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
                            //RobotConnected = false;
                            Robot.IsConnected = false;
                            if (bmanualstop)
                            {
                                return;
                            }
                            break;
                        }
                    }
                    catch (Exception ex)
                    {
                        //RobotConnected = false;
                        Robot.IsConnected = false;
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

        public void ConnectRobot()
        {
            if (thread_RobotServer == null)
            {
                bmanualstop = false;
                thread_RobotServer = new Thread(RobotClient_Start);
                thread_RobotServer.IsBackground = true;
                thread_RobotServer.Start();
            }
            else
            {
                if (thread_RobotServer.IsAlive)
                {
                    //AddLog("勿重複操作");
                }
                else
                {
                    bmanualstop = false;
                    thread_RobotServer = new Thread(RobotClient_Start);
                    thread_RobotServer.IsBackground = true;
                    thread_RobotServer.Start();
                }
            }
        }

        public void SendMsg(string str, bool ClearLast)
        {
            try
            {
                if (ClearLast)
                    Robot.ReceiveMSG_From_Robot = "";

                Byte[] sendByte = new Byte[128];
                string sendToServer = str;
                sendByte = Encoding.ASCII.GetBytes(sendToServer.ToCharArray());
                clientSocket.Send(sendByte, sendByte.Length, 0);

            }
            catch (Exception ex)
            {

                //MessageBox.Show(ex.Message);

            }
        }

        public void DisconnectRobot()
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
