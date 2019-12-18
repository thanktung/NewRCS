using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Data;
using System.Drawing;
using System.Linq;
using System.Text;
using System.Windows.Forms;

namespace RobotMainForm
{
    public partial class 手柄遙控示意圖 : Form
    {
        public 手柄遙控示意圖()
        {
            InitializeComponent();
        }

        private void Form_jogwheelinfo_Load(object sender, EventArgs e)
        {
            pictureBox1.Image = Image.FromFile(Application.StartupPath + "\\Jog\\1.jpg");
            pictureBox2.Image = Image.FromFile(Application.StartupPath + "\\Jog\\2.jpg");
        }
    }
}
