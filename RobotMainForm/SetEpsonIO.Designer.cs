namespace RobotMainForm
{
    partial class SetEpsonIO
    {
        /// <summary>
        /// Required designer variable.
        /// </summary>
        private System.ComponentModel.IContainer components = null;

        /// <summary>
        /// Clean up any resources being used.
        /// </summary>
        /// <param name="disposing">true if managed resources should be disposed; otherwise, false.</param>
        protected override void Dispose(bool disposing)
        {
            if (disposing && (components != null))
            {
                components.Dispose();
            }
            base.Dispose(disposing);
        }

        #region Windows Form Designer generated code

        /// <summary>
        /// Required method for Designer support - do not modify
        /// the contents of this method with the code editor.
        /// </summary>
        private void InitializeComponent()
        {
            this.bt_id = new System.Windows.Forms.Button();
            this.label4 = new System.Windows.Forms.Label();
            this.tBox_name = new System.Windows.Forms.TextBox();
            this.nupdown_num = new System.Windows.Forms.NumericUpDown();
            this.label3 = new System.Windows.Forms.Label();
            this.button1 = new System.Windows.Forms.Button();
            this.label1 = new System.Windows.Forms.Label();
            ((System.ComponentModel.ISupportInitialize)(this.nupdown_num)).BeginInit();
            this.SuspendLayout();
            // 
            // bt_id
            // 
            this.bt_id.Enabled = false;
            this.bt_id.Location = new System.Drawing.Point(256, 10);
            this.bt_id.Name = "bt_id";
            this.bt_id.Size = new System.Drawing.Size(64, 32);
            this.bt_id.TabIndex = 19;
            this.bt_id.Text = "0";
            this.bt_id.UseVisualStyleBackColor = true;
            // 
            // label4
            // 
            this.label4.AutoSize = true;
            this.label4.ForeColor = System.Drawing.Color.DarkCyan;
            this.label4.Location = new System.Drawing.Point(26, 60);
            this.label4.Name = "label4";
            this.label4.Size = new System.Drawing.Size(32, 12);
            this.label4.TabIndex = 18;
            this.label4.Text = "Name";
            // 
            // tBox_name
            // 
            this.tBox_name.Location = new System.Drawing.Point(78, 57);
            this.tBox_name.Name = "tBox_name";
            this.tBox_name.Size = new System.Drawing.Size(159, 22);
            this.tBox_name.TabIndex = 17;
            // 
            // nupdown_num
            // 
            this.nupdown_num.Font = new System.Drawing.Font("Calibri", 9.75F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(0)));
            this.nupdown_num.Location = new System.Drawing.Point(78, 97);
            this.nupdown_num.Maximum = new decimal(new int[] {
            30,
            0,
            0,
            0});
            this.nupdown_num.Name = "nupdown_num";
            this.nupdown_num.Size = new System.Drawing.Size(159, 23);
            this.nupdown_num.TabIndex = 16;
            // 
            // label3
            // 
            this.label3.AutoSize = true;
            this.label3.ForeColor = System.Drawing.Color.DarkCyan;
            this.label3.Location = new System.Drawing.Point(30, 99);
            this.label3.Name = "label3";
            this.label3.Size = new System.Drawing.Size(28, 12);
            this.label3.TabIndex = 14;
            this.label3.Text = "Num";
            // 
            // button1
            // 
            this.button1.BackColor = System.Drawing.Color.WhiteSmoke;
            this.button1.DialogResult = System.Windows.Forms.DialogResult.OK;
            this.button1.Font = new System.Drawing.Font("微软雅黑", 11.25F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(0)));
            this.button1.Location = new System.Drawing.Point(256, 57);
            this.button1.Name = "button1";
            this.button1.Size = new System.Drawing.Size(64, 65);
            this.button1.TabIndex = 12;
            this.button1.Text = "更改";
            this.button1.UseVisualStyleBackColor = false;
            this.button1.Click += new System.EventHandler(this.button1_Click);
            // 
            // label1
            // 
            this.label1.AutoSize = true;
            this.label1.Font = new System.Drawing.Font("微软雅黑", 14.25F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(0)));
            this.label1.Location = new System.Drawing.Point(116, 17);
            this.label1.Name = "label1";
            this.label1.Size = new System.Drawing.Size(88, 25);
            this.label1.TabIndex = 11;
            this.label1.Text = "輸入設置";
            // 
            // SetEpsonIO
            // 
            this.AutoScaleDimensions = new System.Drawing.SizeF(6F, 12F);
            this.AutoScaleMode = System.Windows.Forms.AutoScaleMode.Font;
            this.ClientSize = new System.Drawing.Size(354, 148);
            this.Controls.Add(this.bt_id);
            this.Controls.Add(this.label4);
            this.Controls.Add(this.tBox_name);
            this.Controls.Add(this.nupdown_num);
            this.Controls.Add(this.label3);
            this.Controls.Add(this.button1);
            this.Controls.Add(this.label1);
            this.FormBorderStyle = System.Windows.Forms.FormBorderStyle.FixedToolWindow;
            this.Name = "SetEpsonIO";
            this.StartPosition = System.Windows.Forms.FormStartPosition.Manual;
            this.Text = "SetEpsonIO";
            ((System.ComponentModel.ISupportInitialize)(this.nupdown_num)).EndInit();
            this.ResumeLayout(false);
            this.PerformLayout();

        }

        #endregion

        private System.Windows.Forms.Button bt_id;
        private System.Windows.Forms.Label label4;
        private System.Windows.Forms.TextBox tBox_name;
        private System.Windows.Forms.NumericUpDown nupdown_num;
        private System.Windows.Forms.Label label3;
        private System.Windows.Forms.Button button1;
        private System.Windows.Forms.Label label1;
    }
}