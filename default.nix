let
  nixpkgs = import <nixpkgs> {};
in with nixpkgs;
let
  hackage-cli =
    let src = fetchFromGitHub {
        owner = "hackage-trustees";
        repo = "hackage-cli";
        rev = "5871c72e0f5797e22f24c8beaff6527f82448077";
        sha256 = "01fsiifxjmgvpgs89avnfigx4gv6464rik1vpkb1gy38j2d7dkrz";
      };
    in haskellPackages.callCabal2nix "hackage-cli" src {
      netrc = haskell.lib.dontCheck haskellPackages.netrc;
    };

  scripts = python3Packages.buildPythonPackage {
    pname = "hs-maintainer-tools";
    version = "1.0";
    src = ./.;
    preBuild = ''
      mypy cabal_bump.py
    '';
    buildInputs = [ mypy ];
    propagatedBuildInputs = [
      git curl nix
      cabal-install haskellPackages.haddock
      hackage-cli
    ];
  };
in scripts
