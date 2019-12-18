using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Data;
using System.Drawing;
using System.Linq;
using System.Text;
using System.Windows.Forms;
using AutoMationTest.IO;
using RobotMainForm;

namespace AutoMationTest.UI
{
    public partial class SetIO : Form
    {
        public SetIO()
        {
            InitializeComponent();
        }

        private int _id = 0;
        private string _name = "";
        private int _port = 0;
        private int _num = 0;
        private IOs _ios = IOs.Input;
        public enum IOs
        {
            Input,
            Output
        }



        private void button1_Click(object sender, EventArgs e)
        {
            string _nname = tBox_name.Text.Trim();

            string nport = Convert.ToString(nupdown_port.Value);
            string nnum = Convert.ToString(nupdown_num.Value);
            if (_ios == IOs.Input)
            {

                Program.mainform._myio.SetInputPortNum(this.ID, _nname, nport, nnum);
            }
            else
            {

                Program.mainform._myio.SetOutputPortNum(this.ID, _nname, nport, nnum);
            }
            this.Close();
        }

        public IOs IOSet
        {
            get
            {
                return _ios;
            }
            set
            {
                _ios = value;
                if (_ios == IOs.Input)
                {
                    SetLabelCallback(label1, "輸入設置");
                }
                else
                {
                    SetLabelCallback(label1, "輸出設置");
                }
            }
        }

        public int ID
        {
            get
            {
                return _id;
            }
            set
            {
                _id = value;
                SetButtonCallback(bt_id, _id.ToString());

            }
        }

        public string IOName
        {
            get
            {
                return _name;
            }
            set
            {
                _name = value;
                SetTextBoxCallback(tBox_name, _name);

            }
        }

        public int Port
        {
            get
            {
                return _port;
            }
            set
            {
                _port = value;
                SetNumUpDpwnCallback(nupdown_port, Convert.ToDecimal(_port));
            }
        }

        public int Num
        {
            get
            {
                return _num;
            }
            set
            {
                _num = value;
                SetNumUpDpwnCallback(nupdown_num, Convert.ToDecimal(_num));
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

        delegate void dSetLabelCallback(Label label, string title);
        public void SetLabelCallback(Label label, string title)
        {
            if (label.InvokeRequired)
            {
                dSetLabelCallback d = new dSetLabelCallback(SetLabelCallback);
                label.Invoke(d, new object[] { label, title });
            }
            else
            {
                label.Text = title;
                label.Refresh();
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
    }
}
