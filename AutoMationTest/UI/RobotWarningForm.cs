using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Data;
using System.Drawing;
using System.Linq;
using System.Text;
using System.Windows.Forms;

namespace AutoMationTest.UI
{
    public partial class RobotWarningForm : Form
    {
        public enum MessageButton
        {
            YesNo,
            OK
        }

        public RobotWarningForm(MessageButton mbutton, string Errormsg)
        {
            InitializeComponent();

            try
            {
                switch (mbutton)
                {
                    case MessageButton.OK:
                        button1.Visible = false;
                        button2.Visible = false;
                        break;
                    case MessageButton.YesNo:
                        button3.Visible = false;
                        break;
                }

                label1.Text = Errormsg;
            }
            catch (Exception ex)
            {
                MessageBox.Show(ex.ToString());
            }
        }

    }
}
