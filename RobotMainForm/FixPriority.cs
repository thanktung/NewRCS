using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Drawing;
using System.Data;
using System.Linq;
using System.Text;
using System.Windows.Forms;
using AutoMationTest.Common;
using AutoMationTest.UI;
using System.Threading;

namespace RobotMainForm
{
    public partial class FixPriority : UserControl
    {
        public FixPriority()
        {
            InitializeComponent();
        }

        private const string CategoryName = "優先級設定";
        private int _stationnumber = 1;
        private int _fixPriority = 0;

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
                //StationNum.Text = _stationnumber.ToString();
                SetButtonCallback(StationNum, _stationnumber.ToString());
                int Maxnum = ((int[])Produce.Station.NumberList[Produce.Station.Name[_stationnumber].ToString()]).Length - 1;
                SetNumUpDpwnM(numericUpDown1, Maxnum, 0);
                //numericUpDown1.Minimum = 0;
                //numericUpDown1.Maximum = ((int[])Produce.Station.NumberList[Produce.Station.Name[_stationnumber].ToString()]).Length - 1;
            }
        }

        [Category(CategoryName)]
        [Description("優先級")]
        [DefaultValue(1)]
        public int Priority
        {
            get
            {
                return _fixPriority;
            }
            set
            {
                _fixPriority = value;

                //numericUpDown1.Value = Convert.ToDecimal(_fixPriority);
                SetNumUpDpwnCallback(numericUpDown1, Convert.ToDecimal(_fixPriority));
            }
        }

        private void FixPriority_Load(object sender, EventArgs e)
        {

        }

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
            if (!Produce.bLoginOK || Produce.UserLevel < 3)
            {
                ShowWarmForm("未登录或用户权限不足!");
                return;
            }

            if (button1.Text == "更改")
            {
                numericUpDown1.Enabled = true;

                button1.Text = "確定";
                button1.BackColor = Color.Orange;
            }
            else
            {
                numericUpDown1.Enabled = false;

                int newswt = Convert.ToInt16(numericUpDown1.Value);
                Priority = newswt;
                Produce.SetFixtruePriority(StationNumber, newswt);

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

        delegate void dSetButtonCallback(Button bt, string msg);
        public void SetButtonCallback(Button bt, string msg)
        {
            if (bt.InvokeRequired)
            {
                dSetButtonCallback d = new dSetButtonCallback(SetButtonCallback);
                bt.Invoke(d, new object[] { bt, msg });
            }
            else
            {
                bt.Text = msg;

            }
        }

        delegate void dSetNumUpDpwnCallback(NumericUpDown nupdowm, Decimal value);
        public void SetNumUpDpwnCallback(NumericUpDown nupdowm, Decimal value)
        {
            if (nupdowm.InvokeRequired)
            {
                dSetNumUpDpwnCallback d = new dSetNumUpDpwnCallback(SetNumUpDpwnCallback);
                nupdowm.Invoke(d, new object[] { nupdowm, value });
            }
            else
            {
                nupdowm.Value = value;
            }
        }

        delegate void dSetNumUpDpwnM(NumericUpDown nupdowm, int MAX, int MIN);
        public void SetNumUpDpwnM(NumericUpDown nupdowm, int MAX, int MIN)
        {
            if (nupdowm.InvokeRequired)
            {
                dSetNumUpDpwnM d = new dSetNumUpDpwnM(SetNumUpDpwnM);
                nupdowm.Invoke(d, new object[] { nupdowm, MAX, MIN });
            }
            else
            {
                nupdowm.Maximum = MAX;
                nupdowm.Minimum = MIN;
            }
        }
    }
}
