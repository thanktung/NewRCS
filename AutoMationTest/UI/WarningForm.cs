using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Data;
using System.Drawing;
//using System.Linq;
using System.Text;
using System.Windows.Forms;

namespace AutoMationTest.UI
{
    public partial class WarningForm : Form
    {
        public WarningForm(string msg)
        {
            InitializeComponent();
            label1.Text = msg;
            label1.Refresh();
        }

        private void WarningForm_Load(object sender, EventArgs e)
        {

        }
    }
}
