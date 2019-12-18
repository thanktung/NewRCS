using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Drawing;
using System.Data;
using System.Text;
using System.Windows.Forms;
using AutoMationTest.Common;
using System.Threading;


namespace AutoMationTest.UI
{
    public partial class FixtureSet : UserControl
    {
        public FixtureSet()
        {
            InitializeComponent();
        }
        private const string CategoryName = "治具設定";
        private int _stationnumber = 1;
        private string sIP = "127.0.0.1";
        private int sPort = 5004;
        //private int sTimeout = 500;

        [Category(CategoryName)]
        [Description("治具編號數")]
        [DefaultValue(1)]
        public int StationNumber
        {
            get
            {
                return _stationnumber;
            }
            set
            {
                _stationnumber = value;
                StationNum.Text = _stationnumber.ToString();
            }
        }

        [Category(CategoryName)]
        [Description("ATS所在PC的IP地址")]
        [DefaultValue("127.0.0.1")]
        public string IP
        {
            get
            {
                return sIP;
            }
            set
            {
                sIP = value;
                SetTextBoxCallback(textBox_IP, sIP);
            }
        }

        [Category(CategoryName)]
        [Description("ATS所在PC的網絡端口")]
        [DefaultValue(5004)]
        public int Port
        {
            get
            {
                return sPort;
            }
            set
            {
                sPort = value;
                SetTextBoxCallback(textBox_Port, sPort.ToString());
            }
        }

        //[Category(CategoryName)]
        //[Description("ATS超時時間")]
        //[DefaultValue(500)]
        //public int TimeOut
        //{
        //    get
        //    {
        //        return sTimeout;
        //    }
        //    set
        //    {
        //        sTimeout = value;
        //        textBox_TimeOut.Text = sTimeout.ToString();
        //    }
        //}

        string WarningShowMsg = "";
        private void ShowWarmForm(string WarnMsg)
        {
            Log.AddMainLog("警告:" + WarnMsg);
            WarningShowMsg = WarnMsg;
            Thread thwarn = new Thread(new ThreadStart(ThreadWarmForm));
            thwarn.Start();
        }

        private void ThreadWarmForm()
        {
            WarningForm wf = new WarningForm(WarningShowMsg);
            wf.Show();
            wf.Refresh();
            Thread.Sleep(500);
            wf.Close();
        }
        private void button1_Click(object sender, EventArgs e)
        {
            if (!Produce.bLoginOK || Produce.UserLevel < 4)
            {
                ShowWarmForm("未登录或用户权限不足!");
                return;
            }

            if (button1.Text == "更改")
            {
                textBox_IP.Enabled = true;
                textBox_Port.Enabled = true;
                //textBox_TimeOut.Enabled = true;

                button1.Text = "確定";
                button1.BackColor = Color.Orange;
            }
            else
            {
                textBox_IP.Enabled = false;
                textBox_Port.Enabled = false;
                //textBox_TimeOut.Enabled = false;

                INI.WriteINI(Application.StartupPath + "\\Data","Setting", "ATS_IP_Port", "ATS" + StationNumber.ToString(), textBox_IP.Text + "," + textBox_Port.Text);

                RobotMainForm.Program.mainform.allatsui1.ATS[StationNumber - 1].IP = textBox_IP.Text;
                RobotMainForm.Program.mainform.allatsui1.ATS[StationNumber - 1].Port = Convert.ToInt32(textBox_Port.Text);

                button1.Text = "更改";
                button1.BackColor = Color.LightYellow;
            }
        }

        delegate void dSetTextBoxCallback(TextBox textbox, string msg);
        public void SetTextBoxCallback(TextBox textbox, string msg)
        {
            if (textbox.InvokeRequired)
            {
                dSetTextBoxCallback d = new dSetTextBoxCallback(SetTextBoxCallback);
                textbox.Invoke(d, new object[] { textbox, msg });
            }
            else
            {
                textbox.Text = msg;

            }
        }

    }
}
