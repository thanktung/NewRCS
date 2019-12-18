using System;
using System.Collections.Generic;
using System.Text;
using System.IO.Ports;
using System.Windows.Forms;
using System.Threading;

namespace AutoMationTest.Robots
{
    public class YAMAHA
    {
        public string Comport;
        public int BaudRate;

        SerialPort comm;
        private List<byte> buffer = new List<byte>(4096);
        private long received_count = 0;
        private StringBuilder builder = new StringBuilder();
        Thread ReceiveThread;

        public void ConnectRobot()
        {
            try
            {
                if (comm == null)
                {
                    comm = new SerialPort();
                    comm.PortName = Comport;
                    comm.BaudRate = BaudRate;
                    comm.Parity = Parity.None;
                    comm.DataBits = 8;
                    comm.StopBits = StopBits.One;
                }

                if (!comm.IsOpen)
                {
                    comm.Open();
                    Robot.IsConnected = true;
                    ReceiveThread = new Thread(new ThreadStart(ReceiveDataFromRobot));
                    ReceiveThread.Start();
                }
            }
            catch (Exception ex)
            {
                comm = null;
                MessageBox.Show(ex.Message);
            }
        }

        public void DisconnectRobot()
        {
            Robot.IsConnected = false;
            if (comm != null)
            {
                if (comm.IsOpen)
                {
                    comm.Close();
                }
            }
        }

        public void SendToRobot(string msg, bool ClearLastReceive)
        {
            if (ClearLastReceive)
                Robot.ReceiveMSG_From_Robot = "";

            try
            {
                if (comm.IsOpen)
                {
                    comm.WriteLine(msg);
                }
            }
            catch (Exception ex)
            { }
        }

        private void ReceiveDataFromRobot()
        {

            while (true)
            {

                if (Robot.IsConnected)
                {


                    try
                    {
                        int n = comm.BytesToRead;
                        byte[] buf = new byte[n];
                        received_count += n;
                        comm.Read(buf, 0, n);

                        bool data_1_catched = false;
                        buffer.AddRange(buf);
                        builder.Append(Encoding.ASCII.GetString(buf));

                        if (builder.ToString() != "")
                        {
                            Robot.ReceiveMSG_From_Robot += builder.ToString();
                            builder.Remove(0, builder.Length);
                        }
                    }
                    catch (Exception ex)
                    {
                        Thread.Sleep(10);
                    }

                }
                else
                {
                    break;
                }

            }



        }
    }
}
