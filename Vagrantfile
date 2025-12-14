# Box base Debian 12 (Bookworm)
# https://portal.cloud.hashicorp.com/vagrant/discover/debian/bookworm64

Vagrant.configure("2") do |config|
  # Servidor de origen — 2 vCPUs — 2 GB RAM
  # ===========================================================================
  config.vm.define "genesis" do |node|
    node.vm.box = "debian/bookworm64"
    node.vm.box_version = "12.20250126.1"
    node.vm.hostname = "server-01-genesis"
     # Configurar red en modo bridge (ajustar interfaz e IP según el anfitrión)
    node.vm.network "public_network", bridge: "wlo1", ip: "192.168.0.250"
    
    node.vm.provider "virtualbox" do |vb|
      vb.name = "prog--srv01-genesis"
      vb.memory = 2048
      vb.cpus = 2
    end

    # Habilitar autenticación SSH por contraseña para usuarios "root" y "vagrant"
    # Ejecutado como "root" (privileged: true)
    node.vm.provision "shell", privileged: true, inline: <<-SHELL
      echo 'vagrant:vagrant' | chpasswd
      sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config
      sed -i 's/^#*ChallengeResponseAuthentication.*/ChallengeResponseAuthentication no/' /etc/ssh/sshd_config
      sed -i 's/^#*PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config
      systemctl restart sshd
    SHELL

    # Crear ~/.ssh para el usuario "vagrant"
    # Ejectuado como "vagrant" (prileged: false)
    node.vm.provision "shell", privileged: false, inline: <<-SHELL
      mkdir -p /home/vagrant/.ssh
      chmod 700 /home/vagrant/.ssh
      chown vagrant:vagrant /home/vagrant/.ssh
    SHELL

    # Instalar llave pública para el usuario "vagrant"
    # Vagrant monta automáticamente el directorio del proyecto en /vagrant
    # Ejectuado como "vagrant" (prileged: false)
    node.vm.provision "shell", privileged: false, inline: <<-SHELL
      cat /vagrant/demo_keys/demo_ed25519.pub >> /home/vagrant/.ssh/authorized_keys
      chmod 600 /home/vagrant/.ssh/authorized_keys
      chown vagrant:vagrant /home/vagrant/.ssh/authorized_keys
    SHELL

    # Instalar llave pública para el usuario "root"
    # Vagrant monta automáticamente el directorio del proyecto en /vagrant
    # Ejecutado como "root" (privileged: true)
    node.vm.provision "shell", privileged: true, inline: <<-SHELL
      mkdir -p /root/.ssh
      chmod 700 /root/.ssh
      cat /vagrant/demo_keys/demo_ed25519.pub >> /root/.ssh/authorized_keys
      chmod 600 /root/.ssh/authorized_keys
    SHELL
    
    # Ejecutar instalación de WordPress
    # Ejectuado como "vagrant" (prileged: false)
    node.vm.provision "shell", path:'install_wordpress.sh', privileged: false
  end

  # Servidor de destino | 2 vCPUs | 2 GB RAM
  # ===========================================================================
  config.vm.define "exodus" do |node|
    node.vm.box = "debian/bookworm64"
    node.vm.box_version = "12.20250126.1"
    node.vm.hostname = "server-02-exodus"
    # Configurar red en modo bridge (ajustar interfaz e IP según el anfitrión)
    node.vm.network "public_network", bridge: "wlo1", ip: "192.168.0.251"
    
    node.vm.provider "virtualbox" do |vb|
      vb.name = "prog--srv02-exodus"
      vb.memory = 2048
      vb.cpus = 2
    end
    
    # Habilitar autenticación SSH por contraseña para usuarios "root" y "vagrant"
    # Ejecutado como "root" (privileged: true)
    node.vm.provision "shell", privileged: true, inline: <<-SHELL
      echo 'vagrant:vagrant' | chpasswd
      sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config
      sed -i 's/^#*ChallengeResponseAuthentication.*/ChallengeResponseAuthentication no/' /etc/ssh/sshd_config
      sed -i 's/^#*PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config
      systemctl restart sshd
    SHELL

    # Crear ~/.ssh para el usuario "vagrant"
    # Ejectuado como "vagrant" (prileged: false)
    node.vm.provision "shell", privileged: false, inline: <<-SHELL
      mkdir -p /home/vagrant/.ssh
      chmod 700 /home/vagrant/.ssh
      chown vagrant:vagrant /home/vagrant/.ssh
    SHELL

    # Instalar llave pública para el usuario "vagrant"
    # Vagrant monta automáticamente el directorio del proyecto en /vagrant
    # Ejectuado como "vagrant" (prileged: false)
    node.vm.provision "shell", privileged: false, inline: <<-SHELL
      cat /vagrant/demo_keys/demo_ed25519.pub >> /home/vagrant/.ssh/authorized_keys
      chmod 600 /home/vagrant/.ssh/authorized_keys
      chown vagrant:vagrant /home/vagrant/.ssh/authorized_keys
    SHELL

    # Instalar llave pública para el usuario "root"
    # Vagrant monta automáticamente el directorio del proyecto en /vagrant
    # Ejecutado como "root" (privileged: true)
    node.vm.provision "shell", privileged: true, inline: <<-SHELL
      mkdir -p /root/.ssh
      chmod 700 /root/.ssh
      cat /vagrant/demo_keys/demo_ed25519.pub >> /root/.ssh/authorized_keys
      chmod 600 /root/.ssh/authorized_keys
    SHELL

    # Ejecutar instalación del stack LAMP
    # Ejectuado como "vagrant" (prileged: false)
    node.vm.provision "shell", path:'install_lamp.sh', privileged: false
  end
end
