import { task } from 'hardhat/config';
import { DRE } from '../../helpers/misc-utils';
import { aaveMarketAddresses } from '../../helpers/aave-v2-addresses';
import { getAaveOracle, getLendingPoolConfigurator } from '../../helpers/contract-getters';

task('antei-setup', 'Deploy and Configure Antei').setAction(async (_, hre) => {
  await hre.run('set-DRE');
  const { deployments, ethers } = DRE;

  /*****************************************
   *        DEPLOY DEPENDENT CONTRACTS     *
   ******************************************/

  if (hre.network.name === 'hardhat') {
    await deployments.fixture(['full_antei_deploy']);
  } else {
    console.log('Contracts already deployed!');
  }

  /*****************************************
   *          INITIALIZE RESERVE           *
   ******************************************/
  blankSpace();
  await hre.run('initialize-asd-reserve');

  /*****************************************
   *            Configure Reserve          *
   * 1. enable borrowing                   *
   * 2. configure oracle                   *
   ******************************************/
  blankSpace();
  await hre.run('enable-asd-borrowing');

  blankSpace();
  await hre.run('set-asd-oracle');

  console.log(`\nAntei Setup Complete!\n`);
});

const blankSpace = () => {
  console.log();
};
