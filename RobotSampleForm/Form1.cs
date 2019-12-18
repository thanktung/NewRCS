using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Data;
using System.Drawing;
using System.Linq;
using System.Text;
using System.Windows.Forms;
using AutoMationTest.Common;
using AutoMationTest.Robots;
using System.Threading;

namespace RobotSampleForm
{
    public partial class RobotSample : Form
    {
        public RobotSample()
        {
            InitializeComponent();
        }

        Robot _robot;
        Thread CheckRobotThread;
        public enum textboxtype
        {
            Append,
            text
        }
        bool bconnected = false;

        delegate void _SetTexBoxTextCallback(TextBox tb, string text, textboxtype type);
        public void SetAppendText(TextBox tb, string text, textboxtype type)
        {
            try
            {
                if (tb.InvokeRequired)
                {
                    _SetTexBoxTextCallback d = new _SetTexBoxTextCallback(SetAppendText);
                    this.Invoke(d, new object[] { tb, text, type });
                }
                else
                {
                    if (type == textboxtype.Append)
                    {
                        tb.AppendText(text);
                        tb.ScrollToCaret();// 捲動到最後一個插入位置
                    }
                    else
                    {
                        if (tb.Text != text)
                        {
                            tb.Text = text;
                        }
                    }
                }
            }
            catch (Exception E)
            {
                MessageBox.Show(E.Message);
            }
        }

        delegate void _SetPanelCallback(Panel tb, Color cl);
        public void SetPanel(Panel tb, Color cl)
        {
            try
            {
                if (tb.InvokeRequired)
                {
                    _SetPanelCallback d = new _SetPanelCallback(SetPanel);
                    this.Invoke(d, new object[] { tb, cl });
                }
                else
                {
                    tb.BackColor = cl;
                    tb.Refresh();
                }
            }
            catch (Exception E)
            {
                MessageBox.Show(E.Message);
            }
        }


        private void RobotSample_Load(object sender, EventArgs e)
        {
            Produce.GetStationInfo();

            string[] xx = Produce.Station.NameAll;
            int count = Produce.Station.Count;
            string name = Produce.Station.Name[10].ToString();
            int[] lists = (int[])(Produce.Station.NumberList[Produce.Station.NameAll[0]]);
            int timeout = Convert.ToInt32(Produce.Station.TimeOut[Produce.Station.NameAll[0]]);

            //Log.AddAllDUTLog("123", Log.TestResult.NG);
            //Log.AddNGLog("123","TXCAL","-0.6");

            CheckRobotThread = new Thread(new ThreadStart(CheckRobotConnect));
            CheckRobotThread.Start();
        }

        private void AddLog(string text)
        {
            string dt = DateTime.Now.ToString("yyyyMMdd-HH:mm:ss");
            SetAppendText(textBox3, dt + "  " + text + "\r\n", textboxtype.Append);
            Log.AddMainLog(text);

        }

        private void CheckRobotConnect()
        {
            while (true)
            {
                if (_robot != null)
                {
                    if (Robot.IsConnected)
                    {
                        if (!bconnected)
                        {
                            bconnected = true;
                            SetPanel(panel2, Color.Lime);
                            AddLog("手臂已連接!");
                        }
                        //if (Robot.ReceiveMSG_From_Robot != "")
                        //{
                        SetAppendText(textBox2, Robot.ReceiveMSG_From_Robot, textboxtype.text);
                        //}
                    }
                    else
                    {
                        if (bconnected)
                        {
                            bconnected = false;
                            SetPanel(panel2, Color.DarkRed);
                            AddLog("手臂已斷開!");
                        }
                    }
                }

                Thread.Sleep(20);
            }
        }

        private void trackBar1_Scroll(object sender, EventArgs e)
        {
            this.Opacity = Convert.ToDouble(trackBar1.Value) / 100;

        }

        private void RobotSample_FormClosing(object sender, FormClosingEventArgs e)
        {
            Environment.Exit(0);
        }

        private void button_ChangeEpson_Click(object sender, EventArgs e)
        {

        }

        private void button_connect_Click(object sender, EventArgs e)
        {

        }

    }
}
